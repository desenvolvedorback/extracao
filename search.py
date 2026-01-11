# -------------------- search.py --------------------

"""
Módulo principal que contém a classe SemanticSearcher.
Responsabilidades:
- Extrair texto de PDF/DOCX/TXT
- Fazer chunking com overlap
- Gerar embeddings
- Inserir e salvar em FAISS
- Salvar metadados em SQLite
"""

import os
import sqlite3
import json
import uuid
import numpy as np
from tqdm import tqdm

# bibliotecas externas
import fitz  # PyMuPDF
import docx
from sentence_transformers import SentenceTransformer
import faiss


class SemanticSearcher:
    def __init__(self, index_path='index_data/faiss.index', db_path='index_data/metadata.db', embedding_model_name='all-MiniLM-L6-v2'):
        self.index_path = index_path
        self.db_path = db_path
        self.model = SentenceTransformer(embedding_model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

        # conecta sqlite (cria tabelas se não existirem)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

        # carrega ou cria index FAISS
        if os.path.exists(index_path):
            try:
                self.index = faiss.read_index(index_path)
            except Exception as e:
                print('Falha ao carregar índice, criando novo. Erro:', e)
                self.index = faiss.IndexFlatIP(self.dim)
        else:
            self.index = faiss.IndexFlatIP(self.dim)

        # mapeamento id -> metadata (armazenado no sqlite), mas FAISS precisa de ids inteiros
        # vamos usar posicionamento incremental e persistir via salvar_index
        self.next_id = self._get_next_id()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                uuid TEXT,
                file TEXT,
                page INTEGER,
                text TEXT
            )
        ''')
        self.conn.commit()

    def _get_next_id(self):
        cur = self.conn.cursor()
        cur.execute('SELECT MAX(id) FROM chunks')
        r = cur.fetchone()[0]
        return (r + 1) if r is not None else 0

    def save_index(self):
        # salva FAISS e fecha DB
        faiss.write_index(self.index, self.index_path)
        self.conn.commit()

    def _extract_text(self, path):
        """
        Retorna uma lista de (page_number, text) para o arquivo.
        Para PDF: por página.
        Para DOCX: por parágrafo numerado como página -1 (não tem página fixa).
        Para TXT: trata tudo como um único 'page' = 0 dividido por linhas grandes.
        """
        ext = os.path.splitext(path)[1].lower()
        items = []
        if ext == '.pdf':
            doc = fitz.open(path)
            for i in range(doc.page_count):
                page = doc.load_page(i)
                text = page.get_text('text')
                items.append((i + 1, text))
        elif ext in ['.docx', '.doc']:
            doc = docx.Document(path)
            # junte parágrafos em blocos a cada N parágrafos para não criar chunk por parágrafo
            parags = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
            # vamos agrupar cada 8 parágrafos como um bloco
            block_size = 8
            for idx in range(0, len(parags), block_size):
                block = '\n'.join(parags[idx:idx + block_size])
                items.append((idx // block_size + 1, block))
        else:
            # txt e outros
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                alltext = f.read()
            # split por 1000 linhas de chars
            items.append((1, alltext))
        return items

    def _chunk_text(self, text, page_num, chunk_size=1000, overlap=200):
        """Divide o texto em chunks de tamanho aproximado (caracteres) com overlap."""
        chunks = []
        start = 0
        L = len(text)
        while start < L:
            end = min(start + chunk_size, L)
            snippet = text[start:end].strip()
            if snippet:
                chunks.append({'page': page_num, 'text': snippet})
            if end == L:
                break
            start = end - overlap
        return chunks

    def index_file(self, path):
        """Indexa um único arquivo, retornando número de chunks inseridos."""
        items = self._extract_text(path)
        total_added = 0
        for page_num, text in items:
            # segurança: ignore textos muito curtos
            if not text or len(text.strip()) < 30:
                continue
            chunks = self._chunk_text(text, page_num)
            texts = [c['text'] for c in chunks]
            if not texts:
                continue
            # gerar embeddings em batch
            embeddings = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
            # normalizar embeddings para similaridade cosseno com IndexFlatIP
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms==0] = 1e-9
            embeddings = embeddings / norms

            # adiciona ao FAISS
            n_before = self.index.ntotal
            self.index.add(embeddings.astype('float32'))
            # persist metadata no sqlite, com ids sequenciais
            cur = self.conn.cursor()
            for i, c in enumerate(chunks):
                cur.execute('INSERT INTO chunks (uuid, file, page, text) VALUES (?, ?, ?, ?)',
                            (str(uuid.uuid4()), os.path.basename(path), c['page'], c['text']))
            self.conn.commit()
            total_added += len(chunks)
        # salva índice após cada arquivo para segurança
        self.save_index()
        return total_added

    def search(self, query, top_k=5):
        emb = self.model.encode([query], convert_to_numpy=True)
        emb = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
        D, I = self.index.search(emb.astype('float32'), top_k)
        results = []
        cur = self.conn.cursor()
        for score, idx in zip(D[0], I[0]):
            if idx == -1:
                continue
            # FAISS returns index positions starting at 0 corresponding to the order of insertion
            # our sqlite ids start at 1 and increment; we'll fetch by rowid = idx+1
            rid = idx + 1
            cur.execute('SELECT file, page, text FROM chunks WHERE id = ?', (rid,))
            row = cur.fetchone()
            if not row:
                continue
            results.append({'file': row[0], 'page': row[1], 'text': row[2], 'score': float(score)})
        return results

# -------------------- NOTES --------------------

# - Este código foca em ser funcional. Para arquivos muito grandes (700 páginas), a estratégia de
#   chunk por página e posterior split por caracteres funciona bem, já que cada página vira 1-3 chunks.
# - Se quiser otimizar memória/disco, é possível shardar o índice e manter múltiplos índices por arquivo.
# - Para melhorar a relevância, você pode aumentar chunk_size, usar modelos maiores ou aplicar reranking.

# -------------------- fim --------------------
