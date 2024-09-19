import tkinter as tk
from tkinter import messagebox, ttk, filedialog, simpledialog
import requests
from git import Repo, GitCommandError, InvalidGitRepositoryError
import os
from PIL import Image, ImageTk
from io import BytesIO
import urllib.parse
import webbrowser

class GitHubRepoManager:
    def __init__(self, master):
        self.master = master
        master.title("Gestor de Repositorios GitHub")
        self.token = ""
        self.setup_initial_ui()

    def setup_initial_ui(self):
        self.frame = ttk.Frame(self.master, padding="10")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(self.frame, text="Token de GitHub:").grid(column=0, row=0, sticky=tk.W, pady=5)
        self.token_entry = ttk.Entry(self.frame, width=50, show="*")
        self.token_entry.grid(column=1, row=0, sticky=(tk.W, tk.E), pady=5)

        ttk.Button(self.frame, text="Verificar Token", command=self.verify_token).grid(column=1, row=1, sticky=tk.E, pady=5)

    def verify_token(self):
        self.token = self.token_entry.get()
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        response = requests.get('https://api.github.com/user', headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            self.setup_main_ui(user_data)
        else:
            messagebox.showerror("Error", "Token inválido o error de autenticación")

    def setup_main_ui(self, user_data):
        self.frame.destroy()
        self.frame = ttk.Frame(self.master, padding="10")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Información del usuario
        user_frame = ttk.Frame(self.frame, padding="5")
        user_frame.grid(column=0, row=0, columnspan=2, sticky=(tk.W, tk.E))

        self.user_name = user_data.get('name') or user_data.get('login', 'Usuario')
        ttk.Label(user_frame, text=f"Bienvenido, {self.user_name}").grid(column=1, row=0, sticky=tk.W)

        try:
            avatar_url = user_data['avatar_url']
            response = requests.get(avatar_url)
            img = Image.open(BytesIO(response.content))
            img = img.resize((50, 50), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            avatar_label = ttk.Label(user_frame, image=photo)
            avatar_label.image = photo
            avatar_label.grid(column=0, row=0, padx=(0, 10))
        except Exception as e:
            print(f"No se pudo cargar el avatar: {e}")

        # Frame izquierdo para la lista de repositorios
        left_frame = ttk.Frame(self.frame, padding="10")
        left_frame.grid(column=0, row=1, sticky=(tk.N, tk.S, tk.W, tk.E))

        ttk.Label(left_frame, text="Mis Repositorios:").grid(column=0, row=0, sticky=tk.W, pady=(0, 10))

        # Barra de búsqueda
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_repos)
        search_entry = ttk.Entry(left_frame, textvariable=self.search_var)
        search_entry.grid(column=0, row=1, sticky=(tk.W, tk.E), pady=(0, 5))

        self.repo_buttons_frame = ttk.Frame(left_frame)
        self.repo_buttons_frame.grid(column=0, row=2, sticky=(tk.N, tk.S, tk.W, tk.E))

        # Scrollbar para los botones de repositorios
        self.repo_canvas = tk.Canvas(self.repo_buttons_frame)
        self.repo_scrollbar = ttk.Scrollbar(self.repo_buttons_frame, orient="vertical", command=self.repo_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.repo_canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.repo_canvas.configure(
                scrollregion=self.repo_canvas.bbox("all")
            )
        )

        self.repo_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.repo_canvas.configure(yscrollcommand=self.repo_scrollbar.set)

        self.repo_canvas.pack(side="left", fill="both", expand=True)
        self.repo_scrollbar.pack(side="right", fill="y")

        # Botón de refrescar
        ttk.Button(left_frame, text="Refrescar", command=self.refresh_repos).grid(column=0, row=3, sticky=(tk.W, tk.E), pady=5)

        # Frame derecho para las acciones
        right_frame = ttk.Frame(self.frame, padding="10")
        right_frame.grid(column=1, row=1, sticky=(tk.N, tk.S, tk.W, tk.E))

        ttk.Button(right_frame, text="Crear Nuevo Repositorio", command=self.create_repo_window).grid(column=0, row=0, sticky=(tk.W, tk.E), pady=5)
        ttk.Button(right_frame, text="Clonar Repositorio", command=self.clone_repo_window).grid(column=0, row=1, sticky=(tk.W, tk.E), pady=5)
        
        # Configurar Git con la información del usuario
        os.environ['GIT_AUTHOR_NAME'] = self.user_name
        os.environ['GIT_AUTHOR_EMAIL'] = user_data.get('email') or f"{user_data['login']}@users.noreply.github.com"
        os.environ['GIT_COMMITTER_NAME'] = self.user_name
        os.environ['GIT_COMMITTER_EMAIL'] = user_data.get('email') or f"{user_data['login']}@users.noreply.github.com"

        self.load_repos()
    
    def open_repo_window(self, repo):
        repo_window = tk.Toplevel(self.master)
        repo_window.title(f"Gestionar {repo['name']}")
        
        # Mantener la ventana en primer plano
        repo_window.transient(self.master)
        
        # Frame superior para la URL
        top_frame = ttk.Frame(repo_window, padding="10")
        top_frame.pack(fill=tk.X, expand=False)
        
        # Etiqueta y campo de texto para la URL
        ttk.Label(top_frame, text="URL del Repositorio:").pack(side=tk.LEFT, padx=(0, 5))
        url_var = tk.StringVar(value=repo.get('clone_url', ''))
        url_entry = ttk.Entry(top_frame, textvariable=url_var, state='readonly', width=50)
        url_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        # Botón para copiar la URL
        ttk.Button(top_frame, text="Copiar", command=lambda: self.copy_to_clipboard(url_var.get())).pack(side=tk.RIGHT)
        
        # Frame para la rama predeterminada
        branch_frame = ttk.Frame(repo_window, padding="10")
        branch_frame.pack(fill=tk.X, expand=False)
        
        # Etiqueta para la rama predeterminada
        default_branch_label = ttk.Label(branch_frame, text="Rama predeterminada: Cargando...")
        default_branch_label.pack(side=tk.LEFT)
        
        # Función para actualizar la etiqueta de la rama predeterminada
        def update_default_branch_label():
            default_branch = self.get_default_branch(repo)
            default_branch_label.config(text=f"Rama predeterminada: {default_branch}")

        # Llamar a la función para actualizar la etiqueta inicialmente
        update_default_branch_label()

        # Frame principal para los botones
        main_frame = ttk.Frame(repo_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame izquierdo 
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Botones en el frame izquierdo
        ttk.Button(left_frame, text="Commit", command=lambda: self.git_commit(repo)).pack(fill='x', pady=2)
        ttk.Button(left_frame, text="Push", command=lambda: self.git_push(repo)).pack(fill='x', pady=2)
        ttk.Button(left_frame, text="Pull", command=lambda: self.git_pull(repo)).pack(fill='x', pady=2)
        ttk.Button(left_frame, text="Gestionar Ramas", 
                   command=lambda: self.manage_branches(repo, update_default_branch_label=update_default_branch_label)).pack(fill='x', pady=2)
        
        # Frame derecho
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Botones en el frame derecho
        ttk.Button(right_frame, text="Ver Detalles", command=lambda: self.view_repo_details(repo)).pack(fill='x', pady=2)
        ttk.Button(right_frame, text="Abrir en Navegador", command=lambda: self.open_in_browser(repo)).pack(fill='x', pady=2)
        ttk.Button(right_frame, text="Eliminar Repositorio", command=lambda: self.delete_repo(repo)).pack(fill='x', pady=2)
        ttk.Button(right_frame, text="Cambiar Visibilidad", command=lambda: self.change_visibility(repo)).pack(fill='x', pady=2)    
        
    def copy_to_clipboard(self, text):
        self.master.clipboard_clear()
        self.master.clipboard_append(text)
        messagebox.showinfo("Copiado", "URL copiada al portapapeles")

    def load_repos(self):
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        response = requests.get('https://api.github.com/user/repos', headers=headers)
        if response.status_code == 200:
            self.repos = response.json()
            self.display_repos()
        else:
            messagebox.showerror("Error", "No se pudieron cargar los repositorios")

    def display_repos(self):
        # Limpiar el frame scrollable
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        for repo in self.repos:
            repo_button = ttk.Button(self.scrollable_frame, text=repo['name'], 
                                     command=lambda r=repo: self.open_repo_window(r))
            repo_button.pack(fill='x', padx=5, pady=2)

    def select_repo(self, repo):
        self.selected_repo = repo
        messagebox.showinfo("Repositorio Seleccionado", f"Has seleccionado: {repo['name']}")

    def filter_repos(self, *args):
        search_term = self.search_var.get().lower()
        filtered_repos = [repo for repo in self.repos if search_term in repo['name'].lower()]
        self.display_filtered_repos(filtered_repos)

    def display_filtered_repos(self, filtered_repos):
        # Limpiar el frame scrollable
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        for repo in filtered_repos:
            repo_button = ttk.Button(self.scrollable_frame, text=repo['name'], command=lambda r=repo: self.select_repo(r))
            repo_button.pack(fill='x', padx=5, pady=2)

    def refresh_repos(self):
        self.load_repos()

    def create_repo_window(self):
        create_window = tk.Toplevel(self.master)
        create_window.title("Crear Nuevo Repositorio")
        
        # Mantener la ventana en primer plano
        create_window.transient(self.master)

        ttk.Label(create_window, text="Nombre del Repositorio:").grid(column=0, row=0, padx=5, pady=5)
        repo_name = ttk.Entry(create_window, width=30)
        repo_name.grid(column=1, row=0, padx=5, pady=5)

        ttk.Label(create_window, text="Descripción:").grid(column=0, row=1, padx=5, pady=5)
        repo_description = ttk.Entry(create_window, width=30)
        repo_description.grid(column=1, row=1, padx=5, pady=5)

        private_var = tk.BooleanVar()
        ttk.Checkbutton(create_window, text="Privado", variable=private_var).grid(column=0, row=2, columnspan=2, pady=5)

        ttk.Button(create_window, text="Crear", command=lambda: self.create_repo(repo_name.get(), repo_description.get(), private_var.get())).grid(column=0, row=3, columnspan=2, pady=10)

    def create_repo(self, name, description, private):
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        data = {
            'name': name,
            'description': description,
            'private': private
        }
        response = requests.post('https://api.github.com/user/repos', headers=headers, json=data)
        if response.status_code == 201:
            messagebox.showinfo("Éxito", f"Repositorio '{name}' creado con éxito!")
            self.refresh_repos()
        else:
            messagebox.showerror("Error", "No se pudo crear el repositorio")

    def clone_repo_window(self):
        clone_window = tk.Toplevel(self.master)
        clone_window.title("Clonar Repositorio")
        
        # Mantener la ventana en primer plano
        clone_window.transient(self.master)

        ttk.Label(clone_window, text="URL del Repositorio:").grid(column=0, row=0, padx=5, pady=5)
        repo_url = ttk.Entry(clone_window, width=50)
        repo_url.grid(column=1, row=0, padx=5, pady=5)

        ttk.Label(clone_window, text="Directorio Local:").grid(column=0, row=1, padx=5, pady=5)
        local_dir = ttk.Entry(clone_window, width=50)
        local_dir.grid(column=1, row=1, padx=5, pady=5)
        ttk.Button(clone_window, text="Examinar", command=lambda: local_dir.insert(0, filedialog.askdirectory())).grid(column=2, row=1, padx=5, pady=5)

        ttk.Button(clone_window, text="Clonar", command=lambda: self.clone_repo(repo_url.get(), local_dir.get())).grid(column=0, row=2, columnspan=3, pady=10)

    def clone_repo(self, url, local_dir):
        try:
            Repo.clone_from(url, local_dir)
            messagebox.showinfo("Éxito", f"Repositorio clonado con éxito en {local_dir}")
        except GitCommandError as e:
            messagebox.showerror("Error", f"No se pudo clonar el repositorio: {str(e)}")

    def view_repo_details(self, repo):
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        response = requests.get(repo['url'], headers=headers)
        if response.status_code == 200:
            repo_details = response.json()
            details = f"Nombre: {repo_details['name']}\n"
            details += f"Descripción: {repo_details['description']}\n"
            details += f"Estrellas: {repo_details['stargazers_count']}\n"
            details += f"Forks: {repo_details['forks_count']}\n"
            details += f"Lenguaje principal: {repo_details['language']}\n"
            details += f"Visibilidad: {'Privado' if repo_details['private'] else 'Público'}\n"
            details += f"Creado el: {repo_details['created_at']}\n"
            details += f"Última actualización: {repo_details['updated_at']}\n"
                
            messagebox.showinfo("Detalles del Repositorio", details)
        else:
            messagebox.showerror("Error", "No se pudieron obtener los detalles del repositorio")
    
    def open_in_browser(self, repo):
        webbrowser.open(repo['html_url'])

    def delete_repo(self, repo):
        confirm = messagebox.askyesno("Confirmar", f"¿Está seguro de que desea eliminar el repositorio '{repo['name']}'?")
        if confirm:
            headers = {
                'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            response = requests.delete(repo['url'], headers=headers)
            if response.status_code == 204:
                messagebox.showinfo("Éxito", f"Repositorio '{repo['name']}' eliminado con éxito")
                self.refresh_repos()
            else:
                messagebox.showerror("Error", "No se pudo eliminar el repositorio")

    def change_visibility(self, repo):    
        new_visibility = 'private' if not repo['private'] else 'public'
        confirm = messagebox.askyesno("Confirmar", f"¿Está seguro de que desea cambiar la visibilidad del repositorio '{repo['name']}' a {new_visibility}?")
        if confirm:
            headers = {
                'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            data = {
                'private': not repo['private']
            }
            response = requests.patch(repo['url'], headers=headers, json=data)
            if response.status_code == 200:
                messagebox.showinfo("Éxito", f"Visibilidad del repositorio '{repo['name']}' cambiada a {new_visibility}")
                self.refresh_repos()
            else:
                messagebox.showerror("Error", "No se pudo cambiar la visibilidad del repositorio")

    def git_commit(self, repo):
        try:
            local_path = repo.get('local_path')
            if not local_path or not os.path.exists(local_path):
                local_path = filedialog.askdirectory(title="Seleccione el directorio local del repositorio")
                if not local_path:
                    return

            # Verificar si es un repositorio Git válido
            try:
                git_repo = Repo(local_path)
            except InvalidGitRepositoryError:
                # Si no es un repositorio, ofrecer inicializarlo
                initialize_repo = messagebox.askyesno("Inicializar repositorio", 
                                                    "El directorio seleccionado no es un repositorio Git. ¿Desea inicializar uno?")
                if initialize_repo:
                    git_repo = Repo.init(local_path)  # Inicializar el repositorio
                    messagebox.showinfo("Éxito", "Repositorio Git inicializado exitosamente.")
                else:
                    return

            # Verificar si hay cambios para commitear
            if not git_repo.is_dirty() and len(git_repo.untracked_files) == 0:
                messagebox.showinfo("Información", "No hay cambios para commitear.")
                return

            # Mostrar los archivos modificados y sin seguimiento
            status = git_repo.git.status(porcelain=True)
            files_to_commit = simpledialog.askstring(
                "Archivos para commit",
                f"Archivos modificados y sin seguimiento:\n{status}\n\n"
                "Ingrese los archivos que desea incluir en el commit (separados por comas), "
                "o deje en blanco para incluir todos:",
                parent=self.master
            )

            if files_to_commit is None:
                # Usuario canceló
                return

            # Si se especificaron archivos, añadirlos. Si no, añadir todos.
            if files_to_commit.strip():
                for file in files_to_commit.split(','):
                    git_repo.git.add(file.strip())
            else:
                git_repo.git.add(A=True)

            # Pedir mensaje de commit
            commit_message = simpledialog.askstring("Mensaje de Commit", "Ingrese el mensaje para el commit (puede dejarlo en blanco):")
            if commit_message is None:
                # Usuario canceló
                return

            # Si el mensaje está en blanco, usar un mensaje por defecto
            if commit_message.strip() == "":
                commit_message = "Commit realizado desde la aplicación"

            # Realizar el commit
            if git_repo.is_dirty(untracked_files=True):
                git_repo.git.commit('-m', f'Commit inicial: {commit_message}')
            messagebox.showinfo("Éxito", "Commit realizado con éxito.")

        except GitCommandError as e:
            messagebox.showerror("Error", f"No se pudo realizar el commit: {str(e)}")
        except InvalidGitRepositoryError as e:
            messagebox.showerror("Error", f"No se pudo inicializar el repositorio Git: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error: {str(e)}")

    def git_pull(self, repo):
        try:
            local_path = repo.get('local_path')
            if not local_path or not os.path.exists(local_path):
                local_path = filedialog.askdirectory(title="Seleccione el directorio local del repositorio")
                if not local_path:
                    return

            # Verificar si es un repositorio Git válido
            try:
                git_repo = Repo(local_path)
            except InvalidGitRepositoryError:
                messagebox.showerror("Error", "El directorio seleccionado no es un repositorio Git válido.")
                return
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el repositorio: {str(e)}")
                return
            
            # Obtener todas las ramas remotas
            git_repo.git.fetch('--all')  # Asegurarse de tener la información más reciente del remoto
            remote_branches = []
            for remote in git_repo.remotes:
                for ref in remote.refs:
                    remote_branches.append(ref.remote_head)
            
            # Eliminar duplicados y ordenar
            remote_branches = sorted(list(set(remote_branches)))

            # Imprimir las ramas para depuración
            print("Ramas remotas encontradas:", remote_branches)

            # Si solo hay una rama, usarla directamente
            #if len(remote_branches) == 1:
            #    branch_to_pull = remote_branches[0]
            #else:
                # Si hay múltiples ramas, permitir al usuario seleccionar una
            #    branch_to_pull = simpledialog.askstring("Seleccionar Rama", 
            #                                            "Seleccione la rama de la cual desea hacer pull:",
            #                                            initialvalue=git_repo.active_branch.name)
            #    if not branch_to_pull or branch_to_pull not in remote_branches:
            #        messagebox.showerror("Error", "Rama no válida seleccionada.")
            #        return
            
            # Crear una ventana emergente para el combobox
            popup = tk.Toplevel(self.master)
            popup.title("Seleccionar Rama")
            popup.geometry("300x100")

            # Crear y configurar el combobox
            branch_var = tk.StringVar()
            branch_combobox = ttk.Combobox(popup, textvariable=branch_var)
            branch_combobox['values'] = remote_branches
            branch_combobox.set(git_repo.active_branch.name)  # Valor inicial
            branch_combobox.pack(pady=10)

            # Variable para almacenar la selección
            selected_branch = [None]

            # Función para manejar la selección
            def on_select():
                selected_branch[0] = branch_var.get()
                popup.destroy()

            # Botón para confirmar la selección
            select_button = ttk.Button(popup, text="Seleccionar", command=on_select)
            select_button.pack(pady=5)

            # Esperar a que se cierre la ventana emergente
            popup.wait_window()

            branch_to_pull = selected_branch[0]
            
            if not branch_to_pull or branch_to_pull not in remote_branches:
                messagebox.showerror("Error", "Rama no válida seleccionada.")
                return

            # Verificar si hay cambios locales no confirmados
            if git_repo.is_dirty():
                confirm = messagebox.askyesno("Cambios locales detectados", 
                                            "Se detectaron cambios locales no confirmados. "
                                            "¿Desea confirmar estos cambios antes de hacer pull?")
                if confirm:
                    # Mostrar los cambios al usuario
                    changes = git_repo.git.status(porcelain=True)
                    print(changes)
                    
                    # Pedir al usuario que escriba su mensaje de commit
                    commit_message = simpledialog.askstring("Mensaje de Commit", 
                                                            "Por favor, escriba su mensaje de commit:")
                    
                    if commit_message:
                        # Confirmar cambios locales con el mensaje personalizado
                        git_repo.git.add(A=True)
                        git_repo.git.commit('-m',f'{commit_message}')
                    else:
                        print("Commit cancelado por el usuario.")
                        return
                else:
                    # Descartar cambios locales
                    discard = messagebox.askyesno("Descartar cambios", 
                                                "¿Está seguro de que desea descartar los cambios locales?")
                    if discard:
                        git_repo.git.reset('--hard')
                    else:
                        return

            # Configurar el remoto con la URL autenticada
            repo_url = repo.get('clone_url')
            if not repo_url:
                messagebox.showerror("Error", "No se encontró la URL del repositorio remoto.")
                return

            parsed_url = urllib.parse.urlparse(repo_url)
            authenticated_url = parsed_url._replace(
                netloc=f"{self.token}@{parsed_url.netloc}"
            ).geturl()

            try:
                if 'origin' in git_repo.remotes:
                    origin = git_repo.remotes.origin
                    origin.set_url(authenticated_url)
                else:
                    origin = git_repo.create_remote('origin', authenticated_url)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo configurar el remoto: {str(e)}")
                return

            # Realizar el pull
            try:
                pull_info = origin.pull(branch_to_pull)

                # Verificar si hubo cambios
                if not pull_info[0].flags & pull_info[0].HEAD_UPTODATE:
                    messagebox.showinfo("Pull Exitoso", "Se recibieron cambios del repositorio remoto.")
                else:
                    messagebox.showinfo("Repositorio Actualizado", "El repositorio local ya estaba actualizado con el remoto.")

                # Preguntar al usuario si quiere hacer push de los cambios
                push_confirmed = messagebox.askyesno("Confirmar Push", 
                                                    "¿Desea hacer push de los cambios locales a GitHub?")
                if push_confirmed:
                    push_info = origin.push(refspec=f'{git_repo.active_branch.name}:{branch_to_pull}')
                    print(f"Push realizado: {push_info}")
                    messagebox.showinfo("Éxito", f"Push realizado con éxito en la rama '{branch_to_pull}'.")
                else:
                    print("Push cancelado por el usuario.")

            except GitCommandError as e:
                if "Permission denied" in str(e):
                    messagebox.showerror("Error de Autenticación", "No se pudo autenticar con el repositorio remoto. Verifique sus credenciales.")
                elif "Couldn't find remote ref" in str(e):
                    messagebox.showerror("Error de Pull", f"No se pudo encontrar la referencia remota para la rama '{branch_to_pull}'. Verifique que la rama exista en el repositorio remoto.")
                else:
                    messagebox.showerror("Error", f"No se pudo realizar la operación: {str(e)}")
            except Exception as e:
                messagebox.showerror("Error", f"Ocurrió un error durante la operación: {str(e)}")

        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error general en git_pull: {str(e)}")
        
    def git_push(self, repo):
        try:
            local_path = repo.get('local_path')
            if not local_path or not os.path.exists(local_path):
                local_path = filedialog.askdirectory(title="Seleccione el directorio local del repositorio")
                if not local_path:
                    return

            # Verificar si es un repositorio Git válido
            try:
                git_repo = Repo(local_path)
            except InvalidGitRepositoryError:
                messagebox.showerror("Error", "El directorio seleccionado no es un repositorio Git válido.")
                return

            # Verificar si hay cambios para pushear
            if not git_repo.is_dirty() and len(git_repo.untracked_files) == 0 and not git_repo.head.is_detached:
                status = git_repo.git.status()
                if "Your branch is up to date" in status:
                    messagebox.showinfo("Información", "No hay cambios para subir al repositorio remoto.")
                    return

            # Obtener la rama actual
            current_branch = git_repo.active_branch.name

            # Preguntar al usuario si quiere hacer push
            push_confirmed = messagebox.askyesno("Confirmar Push", 
                                                f"¿Desea hacer push de la rama '{current_branch}' al repositorio remoto?")
            if not push_confirmed:
                return

            # Obtener la URL del repositorio del objeto repo
            repo_url = repo.get('clone_url')
            if not repo_url:
                messagebox.showerror("Error", "No se encontró la URL del repositorio remoto.")
                return
            
            # Modificar la URL del repositorio para incluir el token
            parsed_url = urllib.parse.urlparse(repo_url)
            authenticated_url = parsed_url._replace(
                netloc=f"{self.token}@{parsed_url.netloc}"
            ).geturl()

            # Configurar el remoto con la URL autenticada
            if 'origin' in git_repo.remotes:
                origin = git_repo.remotes.origin
                origin.set_url(authenticated_url)
            else:
                origin = git_repo.create_remote('origin', authenticated_url)

            # Realizar el push
            push_info = origin.push(refspec=f'{current_branch}:{current_branch}')
            
            # Verificar el resultado del push
            if push_info[0].flags & push_info[0].ERROR:
                raise GitCommandError("git push", push_info[0].summary)

            messagebox.showinfo("Éxito", f"Push realizado con éxito a la rama '{current_branch}'.")

        except GitCommandError as e:
            if "Permission denied (publickey)" in str(e):
                messagebox.showerror("Error de Autenticación", "No se pudo autenticar con el repositorio remoto. Verifique sus credenciales SSH.")
            elif "rejected" in str(e):
                messagebox.showerror("Error de Push", "El push fue rechazado. Puede que necesite hacer un pull primero.")
            else:
                messagebox.showerror("Error", f"No se pudo realizar el push: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error: {str(e)}")

    def manage_branches(self, repo, existing_window=None, update_default_branch_label=None):
        self.selected_repo = repo  # Guardar el repositorio seleccionado
        
        if existing_window:
            branches_window = existing_window
            # Clear existing content
            for widget in branches_window.winfo_children():
                widget.destroy()
        else:
            branches_window = tk.Toplevel(self.master)
            branches_window.title(f"Gestionar Ramas - {repo['name']}")
            # Mantener la ventana en primer plano
            branches_window.transient(self.master)

        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        response = requests.get(f"{repo['url']}/branches", headers=headers)
        if response.status_code == 200:
            branches = response.json()

            for branch in branches:
                branch_frame = ttk.Frame(branches_window)
                branch_frame.pack(fill='x', padx=5, pady=2)
                    
                ttk.Label(branch_frame, text=branch['name']).pack(side='left')
                ttk.Button(branch_frame, text="Eliminar", command=lambda b=branch: self.delete_branch(b, branches_window)).pack(side='right')
                ttk.Button(branch_frame, text="Establecer como predeterminada", command=lambda b=branch: self.set_default_branch(b, branches_window, update_default_branch_label)).pack(side='right')
                
            ttk.Button(branches_window, text="Crear Nueva Rama", command=lambda: self.create_branch(branches_window)).pack(pady=10)
            
            if update_default_branch_label:
                branches_window.after(100, update_default_branch_label)
                
        else:
            messagebox.showerror("Error", "No se pudieron obtener las ramas del repositorio")

    def delete_branch(self, branch, branches_window):
        confirm = messagebox.askyesno("Confirmar", f"¿Está seguro de que desea eliminar la rama '{branch['name']}'?")
        if confirm:
            headers = {
                'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            response = requests.delete(f"{self.selected_repo['url']}/git/refs/heads/{branch['name']}", headers=headers)
            if response.status_code == 204:
                messagebox.showinfo("Éxito", f"Rama '{branch['name']}' eliminada con éxito")
                self.manage_branches(self.selected_repo, branches_window)  # Refresh the branches window
            else:
                messagebox.showerror("Error", "No se pudo eliminar la rama")

    def set_default_branch(self, branch, branches_window, update_default_branch_label=None):
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        data = {
            'default_branch': branch['name']
        }
        response = requests.patch(self.selected_repo['url'], headers=headers, json=data)
        if response.status_code == 200:
            messagebox.showinfo("Éxito", f"Rama '{branch['name']}' establecida como predeterminada")
            if update_default_branch_label:
                update_default_branch_label()
            self.manage_branches(self.selected_repo, branches_window, update_default_branch_label)  # Actualizar la ventana de ramas
        else:
            messagebox.showerror("Error", "No se pudo establecer la rama como predeterminada")

    def create_branch(self, branches_window):
        new_branch_name = simpledialog.askstring("Nueva Rama", "Nombre de la nueva rama:")
        if new_branch_name:
            headers = {
                'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            # Primero, obtener la rama predeterminada del repositorio
            response = requests.get(self.selected_repo['url'], headers=headers)
            if response.status_code == 200:
                default_branch = response.json()['default_branch']
                # Ahora, obtener el SHA del último commit en la rama predeterminada
                response = requests.get(f"{self.selected_repo['url']}/git/refs/heads/{default_branch}", headers=headers)
                if response.status_code == 200:
                    default_branch_sha = response.json()['object']['sha']
                    # Crear la nueva rama
                    data = {
                        'ref': f'refs/heads/{new_branch_name}',
                        'sha': default_branch_sha
                    }
                    response = requests.post(f"{self.selected_repo['url']}/git/refs", headers=headers, json=data)
                    if response.status_code == 201:
                        messagebox.showinfo("Éxito", f"Rama '{new_branch_name}' creada con éxito")
                        self.manage_branches(self.selected_repo, branches_window)  # Refrescar la ventana de ramas
                    else:
                        messagebox.showerror("Error", f"No se pudo crear la nueva rama. Código de estado: {response.status_code}")
                else:
                    messagebox.showerror("Error", f"No se pudo obtener la referencia de la rama predeterminada. Código de estado: {response.status_code}")
            else:
                messagebox.showerror("Error", f"No se pudo obtener la información del repositorio. Código de estado: {response.status_code}")
    
    def get_default_branch(self, repo):
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        response = requests.get(repo['url'], headers=headers)
        if response.status_code == 200:
            repo_data = response.json()
            return repo_data.get('default_branch', 'N/A')
        else:
            return 'Error al obtener la rama'

if __name__ == "__main__":
    root = tk.Tk()
    app = GitHubRepoManager(root)
    root.mainloop()