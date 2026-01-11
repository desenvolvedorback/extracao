from flask import Flask, request, render_template_string
import os
from search import SemanticSearcher

UPLOAD_FOLDER = 'uploads'
INDEX_FOLDER = 'index_data'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(INDEX_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

searcher = SemanticSearcher(index_path=os.path.join(INDEX_FOLDER, 'faiss.index'),
                            db_path=os.path.join(INDEX_FOLDER, 'metadata.db'))

HTML = '''
<!doctype html>
<title>Busca em arquivos</title>
<h2>Upload de arquivos (PDF, DOCX, TXT)</h2>
<form action="/upload" method="post" enctype="multipart/form-data">
  <input type="file" name="file" />
  <input type="submit" value="Upload e indexar" />
</form>

<h2>Pesquisar</h2>
<form action="/search" method="post">
  <input name="query" style="width:60%" placeholder="Digite sua pergunta..." />
  <input type="submit" value="Pesquisar" />
</form>

<div>
{% if results %}
  <h3>Resultados para: {{query}}</h3>
  <ol>
  {% for r in results %}
    <li>
      <b>Arquivo:</b> {{r.file}} — <b>Página/Chunk:</b> {{r.page}} — <b>Score:</b> {{"{:.3f}".format(r.score)}}<br>
      <pre style="white-space:pre-wrap;max-width:800px">{{r.snippet}}</pre>
    </li>
  {% endfor %}
  </ol>
{% endif %}
</div>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/upload', methods=['POST'])
def upload_file():
    f = request.files.get('file')
    if not f:
        return 'Nenhum arquivo enviado', 400
    filename = f.filename
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    f.save(save_path)
    added = searcher.index_file(save_path)
    return f'Arquivo "{filename}" salvo e indexado. Inseridos {added} chunks. <a href="/">Voltar</a>'

@app.route('/search', methods=['POST'])
def do_search():
    q = request.form.get('query')
    if not q:
        return 'Query vazia', 400
    hits = searcher.search(q, top_k=10)
    results = []
    for h in hits:
        results.append({
            'file': h['file'],
            'page': h['page'],
            'score': h['score'],
            'snippet': h['text']
        })
    return render_template_string(HTML, results=results, query=q)

if __name__ == '__main__':
    app.run(debug=True)