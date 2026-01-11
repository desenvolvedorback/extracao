# -------------------- ingest.py --------------------

"""
Script de ingestão em lote. Usa a mesma lógica do searcher para indexar toda uma pasta.
"""

import argparse
import os
from search import SemanticSearcher

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', required=True, help='Pasta com arquivos para indexar')
    parser.add_argument('--index', default='index_data/faiss.index')
    parser.add_argument('--db', default='index_data/metadata.db')
    args = parser.parse_args()

    os.makedirs('index_data', exist_ok=True)
    searcher = SemanticSearcher(index_path=args.index, db_path=args.db)

    total = 0
    for fname in os.listdir(args.dir):
        path = os.path.join(args.dir, fname)
        if os.path.isfile(path):
            try:
                added = searcher.index_file(path)
                print(f'Indexado {fname}: {added} chunks')
                total += added
            except Exception as e:
                print(f'Erro ao indexar {fname}: {e}')
    print('Total chunks indexados:', total)