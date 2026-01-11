import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import re
import queue

class LeitorCredenciaisApp:
    def __init__(self, master):
        self.master = master
        master.title("Leitor de Credenciais TXT")

        self.arquivo_path = None
        self.parar_busca = False
        self.result_queue = queue.Queue()
        self.credenciais_vistas = set()  # <- Aqui armazenamos as credenciais únicas

        # Layout
        self.btn_carregar = tk.Button(master, text="Carregar Arquivo", command=self.carregar_arquivo)
        self.btn_carregar.pack(pady=5)

        self.entry_valor = tk.Entry(master, width=50)
        self.entry_valor.pack(pady=5)
        self.entry_valor.insert(0, "Digite a palavra-chave")
        self.entry_valor.bind("<FocusIn>", self.limpar_placeholder)

        self.btn_buscar = tk.Button(master, text="Buscar", command=self.iniciar_busca)
        self.btn_buscar.pack(pady=5)

        self.btn_limpar = tk.Button(master, text="Limpar Busca", command=self.limpar_resultados)
        self.btn_limpar.pack(pady=5)

        self.btn_parar = tk.Button(master, text="Parar Busca", command=self.parar_busca_funcao, state=tk.DISABLED)
        self.btn_parar.pack(pady=5)

        self.resultado_text = scrolledtext.ScrolledText(master, width=100, height=20)
        self.resultado_text.pack(pady=10)

        self.status = tk.Label(master, text="Pronto", fg="green")
        self.status.pack()

        self.master.after(100, self.atualizar_interface)

    def limpar_placeholder(self, event):
        if self.entry_valor.get() == "Digite a palavra-chave":
            self.entry_valor.delete(0, tk.END)

    def carregar_arquivo(self):
        self.arquivo_path = filedialog.askopenfilename(filetypes=[("Arquivos TXT", "*.txt")])
        if self.arquivo_path:
            messagebox.showinfo("Arquivo carregado", f"Arquivo:\n{self.arquivo_path}")

    def iniciar_busca(self):
        if not self.arquivo_path:
            messagebox.showwarning("Aviso", "Carregue um arquivo primeiro.")
            return

        valor = self.entry_valor.get().strip().lower()
        if not valor or valor == "Digite a palavra-chave":
            messagebox.showwarning("Aviso", "Digite uma palavra para buscar.")
            return

        self.resultado_text.delete('1.0', tk.END)
        self.status.config(text="Buscando...", fg="blue")
        self.btn_buscar.config(state=tk.DISABLED)
        self.btn_parar.config(state=tk.NORMAL)
        self.parar_busca = False
        self.credenciais_vistas.clear()

        while not self.result_queue.empty():
            self.result_queue.get()

        threading.Thread(target=self.buscar_credenciais, args=(valor,), daemon=True).start()

    def limpar_resultados(self):
        self.resultado_text.delete('1.0', tk.END)
        self.entry_valor.delete(0, tk.END)
        self.status.config(text="Pronto", fg="green")

    def parar_busca_funcao(self):
        self.parar_busca = True
        self.status.config(text="Busca cancelada", fg="red")
        self.btn_parar.config(state=tk.DISABLED)

    def buscar_credenciais(self, valor):
        try:
            with open(self.arquivo_path, 'r', encoding='utf-8', errors='ignore') as arquivo:
                for linha in arquivo:
                    if self.parar_busca:
                        break

                    cred = self.extrair_credenciais(linha)
                    if cred:
                        chave = (cred["URL"], cred["USER"], cred["PASS"])
                        if chave in self.credenciais_vistas:
                            continue  # já foi vista
                        self.credenciais_vistas.add(chave)

                        if any(valor in cred[c].lower() for c in ["URL", "USER", "PASS"]):
                            resultado = f"URL: {cred['URL']}\nUSER: {cred['USER']}\nPASS: {cred['PASS']}\n---\n"
                            self.result_queue.put(resultado)
        except Exception as e:
            self.result_queue.put(f"[ERRO]: {e}")
        finally:
            self.result_queue.put("[FIM]")

    def atualizar_interface(self):
        try:
            while not self.result_queue.empty():
                resultado = self.result_queue.get()
                if resultado == "[FIM]":
                    if not self.parar_busca:
                        self.status.config(text="Busca concluída", fg="green")
                    self.btn_buscar.config(state=tk.NORMAL)
                    self.btn_parar.config(state=tk.DISABLED)
                elif resultado.startswith("[ERRO]"):
                    messagebox.showerror("Erro", resultado)
                    self.btn_buscar.config(state=tk.NORMAL)
                    self.btn_parar.config(state=tk.DISABLED)
                    self.status.config(text="Erro durante a busca", fg="red")
                else:
                    self.resultado_text.insert(tk.END, resultado)
                    self.resultado_text.yview(tk.END)
        except Exception as e:
            print(f"Erro na atualização da interface: {e}")
        finally:
            self.master.after(100, self.atualizar_interface)

    def extrair_credenciais(self, linha):
        try:
            linha = linha.strip()

            # Caso 1: linha única com chaves URL, USER, PASS
            if "URL:" in linha and "USER:" in linha and "PASS:" in linha:
                url_match = re.search(r"URL:\s*(\S+)", linha)
                user_match = re.search(r"USER:\s*(\S+)", linha)
                pass_match = re.search(r"PASS:\s*(\S+)", linha)
                if url_match and user_match and pass_match:
                    return {
                        "URL": url_match.group(1),
                        "USER": user_match.group(1),
                        "PASS": pass_match.group(1)
                    }

            # Caso 2: cada campo em linha separada
            if linha.startswith("URL:"):
                self.ultima_url = linha.replace("URL:", "").strip()
                return None
            elif linha.startswith("USER:"):
                self.ultimo_user = linha.replace("USER:", "").strip()
                return None
            elif linha.startswith("PASS:") and hasattr(self, 'ultima_url') and hasattr(self, 'ultimo_user'):
                senha = linha.replace("PASS:", "").strip()
                cred = {
                    "URL": self.ultima_url,
                    "USER": self.ultimo_user,
                    "PASS": senha
                }
                del self.ultima_url
                del self.ultimo_user
                return cred

            # Caso 3: compacta URL:USER:PASS
            if linha.count(":") == 2 and not any(p in linha for p in ["URL", "USER", "PASS"]):
                partes = linha.split(":")
                url, user, passwd = partes
                return {
                    "URL": url.strip(),
                    "USER": user.strip(),
                    "PASS": passwd.strip()
                }

        except Exception as e:
            print(f"Erro ao extrair credenciais: {e}")

        return None

# Iniciar o app
if __name__ == "__main__":
    root = tk.Tk()
    app = LeitorCredenciaisApp(root)
    root.mainloop()
