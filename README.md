# -------------------- README.md --------------------


Projeto: Busca semântica simples para arquivos longos (PDF, DOCX, TXT).
Foco: funcionalidade, escalabilidade para arquivos grandes (até 700 páginas) e suporte a múltiplos arquivos.


Requisitos (use um virtualenv):


pip install -r requirements.txt


Como rodar localmente:


1. Ingestão (indexa arquivos):
- Rode `python ingest.py --dir uploads` para indexar todos os arquivos numa pasta `uploads/`.
2. Executar o servidor web:
- `python app.py` (Flask roda em http://127.0.0.1:5000)
3. Na web UI, envie consultas e obtenha as páginas e trechos.


Arquitetura simples:
- Extrai texto por página (para PDF) ou por parágrafo (DOCX/TXT).
- Chunking por caracteres com overlap para manter contexto em trechos longos.
- Gera embeddings com sentence-transformers (`all-MiniLM-L6-v2`).
- Armazena embeddings em FAISS (IndexFlatIP, com normalização para similaridade de cosseno).
- Metadados (arquivo, página, trecho, posição) salvos em SQLite.


Limitações/Notas:
- Projeto minimalista e local — não inclui autenticação nem UI bonita.
- Para rodar em produção, acrescente verificação de arquivos, quotas, backup do índice e segurança.

````

SE USAR DE OS CREDITOS

````
By Davi Leonardo
