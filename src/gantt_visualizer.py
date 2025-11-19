import json
from datetime import datetime, timedelta
import os
from pathlib import Path
import shutil  # Pour obtenir la taille du terminal

# Imports conditionnels pour matplotlib (maintenant optionnels)
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class GanttVisualizer:
    """
    Classe pour visualiser les diagrammes de Gantt générés par l'application
    """
    
    def __init__(self, console=None):
        self.console = console
        
        # Initialiser matplotlib si disponible
        if HAS_MATPLOTLIB:
            plt.style.use('ggplot')
    
    def load_gantt_data(self, json_file_path):
        """
        Charge les données du diagramme de Gantt à partir d'un fichier JSON
        """
        with open(json_file_path, 'r', encoding='utf-8') as f:
            gantt_data = json.load(f)
        return gantt_data
    
    def create_ascii_gantt(self, gantt_data, title="Diagramme de Gantt de la recette"):
        """
        Crée une représentation ASCII du diagramme de Gantt
        """
        # Extraire les tâches
        tasks = gantt_data.get('tasks', [])
        if not tasks:
            return "Aucune tâche trouvée dans les données du diagramme de Gantt"
        
        # Tenter d'obtenir la largeur du terminal (ou utiliser une valeur par défaut)
        try:
            terminal_width = shutil.get_terminal_size().columns
            terminal_width = min(terminal_width, 150)  # Ne pas dépasser 150 caractères
        except Exception:
            terminal_width = 100  # Largeur par défaut si impossible de détecter
        
        # Nombre de colonnes pour la timeline (laisse de l'espace pour les descriptions)
        name_width = 30  # Largeur exacte de 30 caractères pour les noms des tâches, comme demandé
        
        # Créer un dictionnaire pour stocker les positions de chaque tâche
        task_positions = {}
        dependency_lines = []
        
        # Générer l'en-tête ASCII
        ascii_output = []
        ascii_output.append("=" * terminal_width)
        ascii_output.append(f"{title:^{terminal_width}}")
        ascii_output.append("=" * terminal_width)
        ascii_output.append("")
        
        # Déterminer la durée maximale pour les échelles
        max_duration = max(task.get('duration', 0) for task in tasks)
        total_duration = sum(task.get('duration', 0) for task in tasks)
        
        # Recueillir les identifiants des tâches pour les références de dépendance
        task_id_map = {}
        for i, task in enumerate(tasks):
            task_id = task.get('id', f"task{i+1}")
            task_id_map[task_id] = i
        
        # Pour chaque tâche, générer une ligne dans le diagramme
        for i, task in enumerate(tasks):
            task_id = task.get('id', f"task{i+1}")
            
            # Utiliser le champ short_description s'il existe, sinon utiliser name
            if "short_description" in task:
                task_name = task.get("short_description", "")
            else:
                task_name = task.get('name', f"Tâche {i+1}")
            
            # S'assurer que le nom n'excède pas la largeur spécifiée
            if len(task_name) > name_width:
                task_name = task_name[:name_width-3] + "..."
            elif len(task_name) < name_width:
                # Compléter avec des espaces pour avoir exactement name_width caractères
                task_name = task_name.ljust(name_width)
            
            # Obtenir la durée de la tâche
            task_duration = task.get('duration', 0)
            
            # Créer la barre avec des "=" (1 "=" = 1 minute)
            # Arrondir au supérieur pour les durées non entières
            equal_count = max(1, int(task_duration + 0.99))
            
            # Ajouter la durée au début de la barre
            duration_label = f"{task_duration:.0f}m"
            if equal_count >= len(duration_label) + 2:
                # Si la barre est assez longue, insérer la durée
                prefix = "=" * 1
                suffix = "=" * (equal_count - len(duration_label) - 1)
                bar = prefix + duration_label + suffix
            else:
                bar = "=" * equal_count
            
            # Ajouter la ligne au diagramme
            task_line = f"{task_name} | {bar}"
            ascii_output.append(task_line)
            
            # Stocker la position de la tâche pour les dépendances
            task_positions[task_id] = {
                "line_index": len(ascii_output) - 1,
                "bar_start": name_width + 3  # Position du début de la barre (nom + " | ")
            }
            
            # Collecter les dépendances pour les traiter après
            predecessors = task.get('predecessors', [])
            for pred in predecessors:
                if pred in task_id_map:
                    dependency_lines.append((pred, task_id))
        
        # Au lieu de tracer des lignes complexes pour les dépendances, ajoutons simplement une annotation claire après chaque tâche
        # Créer un dictionnaire pour stocker les dépendances de chaque tâche
        task_dependencies = {}
        for task_id, task_details in task_positions.items():
            # Récupérer les prédécesseurs
            task_idx = 0
            for i, task in enumerate(tasks):
                if task.get('id', f"task{i+1}") == task_id:
                    task_idx = i
                    break
                    
            predecessors = tasks[task_idx].get('predecessors', [])
            if predecessors:
                task_dependencies[task_id] = predecessors
        
        # Mettre à jour les lignes avec les annotations de dépendance
        for task_id, dependencies in task_dependencies.items():
            if task_id in task_positions:
                line_idx = task_positions[task_id]["line_index"]
                line = ascii_output[line_idx]
                
                # Trouver la fin de la barre
                bar_end_pos = line.find(" ", name_width + 3)
                if bar_end_pos == -1:
                    bar_end_pos = len(line)
                
                # Formatage plus clair des dépendances
                dependency_names = []
                for dep_id in dependencies:
                    # Trouver la tâche correspondante pour obtenir son nom court
                    for task_index, task in enumerate(tasks):
                        if task.get('id', f"task{task_index+1}") == dep_id:
                            # Utiliser les 5 premiers caractères du nom de la tâche pour l'identifier
                            task_short_name = task.get('short_description', task.get('name', f"Tâche {task_index+1}"))
                            task_short_id = f"{dep_id}:{task_short_name[:5]}"
                            dependency_names.append(task_short_id)
                            break
                
                if not dependency_names:
                    dependency_names = dependencies  # Utiliser juste les IDs si on ne trouve pas les noms
                
                dependencies_str = " ⬅ " + ", ".join(dependency_names)
                
                # S'assurer que nous avons assez d'espace
                if bar_end_pos + len(dependencies_str) <= terminal_width:
                    # Mettre la dépendance sur la même ligne
                    new_line = line[:bar_end_pos] + dependencies_str + line[bar_end_pos+len(dependencies_str):]
                    ascii_output[line_idx] = new_line[:terminal_width]
                else:
                    # Si pas assez d'espace sur la même ligne, ajouter une ligne en dessous
                    dep_line = " " * (name_width + 3) + "Requiert: " + ", ".join(dependency_names)
                    if line_idx + 1 < len(ascii_output):
                        ascii_output.insert(line_idx + 1, dep_line[:terminal_width])
                    else:
                        ascii_output.append(dep_line[:terminal_width])
                    
                    # Mettre à jour les positions des tâches qui suivent
                    for tid, pos in task_positions.items():
                        if pos["line_index"] > line_idx:
                            pos["line_index"] += 1
        
        # Ajouter des informations supplémentaires et une légende claire
        ascii_output.append("")
        ascii_output.append("-" * terminal_width)
        ascii_output.append(f"Légende: • Chaque '=' représente 1 minute  • Durée totale estimée: {total_duration} minutes")
        ascii_output.append(f"         • La notation 'ID:Nom' après '⬅' indique les dépendances (étapes préalables requises)")
        ascii_output.append("=" * terminal_width)
        
        # Joindre toutes les lignes et renvoyer
        return "\n".join(ascii_output)
    
    def save_ascii_gantt(self, ascii_content, output_path=None, recipe_name=None):
        """
        Sauvegarde la représentation ASCII du diagramme de Gantt dans un fichier texte
        """
        # Si aucun chemin n'est spécifié, générer un nom de fichier basé sur le nom de la recette
        if output_path is None:
            # Créer un dossier pour les visuels ASCII s'il n'existe pas
            ascii_dir = "gantt_ascii"
            os.makedirs(ascii_dir, exist_ok=True)
            
            # Générer un nom de fichier
            safe_name = "gantt"
            if recipe_name:
                safe_name = "".join([c if c.isalnum() else "_" for c in recipe_name])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"{ascii_dir}/{safe_name}_{timestamp}.txt"
        
        # Sauvegarder le contenu ASCII
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ascii_content)
        
        return output_path
    
    def visualize_gantt(self, gantt_data, title="Diagramme de Gantt de la recette"):
        """
        Visualise un diagramme de Gantt à partir des données
        """
        # Vérifier si matplotlib est disponible
        if not HAS_MATPLOTLIB:
            if self.console:
                self.console.print("[yellow]Matplotlib n'est pas disponible, utilisation du mode ASCII uniquement[/yellow]")
            return None
            
        # Extraire les tâches
        tasks = gantt_data.get('tasks', [])
        if not tasks:
            if self.console:
                self.console.print("[red]Aucune tâche trouvée dans les données du diagramme de Gantt[/red]")
            return None
            
        # Paramètres de la figure
        fig, ax = plt.subplots(figsize=(14, max(8, len(tasks) * 0.6 + 2)))
        
        # Utiliser un fond plus clair et agréable
        fig.set_facecolor('#f9f9f9')
        ax.set_facecolor('#f0f0f0')
        
        # Couleurs pour les barres - utiliser une palette plus douce
        colors = plt.cm.tab20c.colors
        
        # Pour chaque tâche, ajouter une barre
        for i, task in enumerate(tasks):
            # Extraire les informations de la tâche
            task_id = task.get('id', f"Task{i}")
            task_name = task.get('name', f"Tâche {i}")
            task_start_str = task.get('start', datetime.now().strftime("%Y-%m-%d %H:%M"))
            task_duration = task.get('duration', 1)  # durée en minutes
            
            # Convertir la date de début en objet datetime
            try:
                task_start = datetime.strptime(task_start_str, "%Y-%m-%d %H:%M")
            except ValueError:
                task_start = datetime.now()
            
            # Calculer la date de fin
            task_end = task_start + timedelta(minutes=task_duration)
            
            # Récupérer les dépendances pour cette tâche
            predecessors = task.get('predecessors', [])
            
            # Ajouter la barre pour cette tâche
            bar_color = colors[i % len(colors)]
            bar = ax.barh(i, (task_end - task_start).total_seconds() / 60, 
                         left=mdates.date2num(task_start),
                         color=bar_color, 
                         edgecolor='black', 
                         alpha=0.9,
                         height=0.6)
            
            # Ajouter le numéro de l'étape et le nom de la tâche
            task_num = task.get('id', str(i+1))
            short_name = task_name[:40] + '...' if len(task_name) > 40 else task_name
            ax.text(mdates.date2num(task_start), i, f" {task_num}. {short_name}", 
                   va='center', ha='left', fontsize=9, color='black', fontweight='bold')
            
            # Ajouter la durée à l'intérieur de la barre si assez longue
            duration_min = task.get('duration', 0)
            if duration_min >= 5:  # Seulement pour les tâches de 5 min ou plus
                ax.text(mdates.date2num(task_start) + (task_end - task_start).total_seconds() / (60*2) / 1440,
                       i, f"{duration_min} min", ha='center', va='center', color='black',
                       fontsize=8, fontweight='bold')
        
        # Formater l'axe des x pour afficher les heures et minutes
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
        # Déterminer dynamiquement l'intervalle des minutes en fonction du nombre de tâches
        # et de la durée totale pour éviter l'erreur MAXTICKS
        total_minutes = sum(task.get('duration', 1) for task in tasks)
        interval = max(15, total_minutes // 10)  # Au moins toutes les 15 min, ou diviser la durée totale en ~10 ticks
        
        # Utiliser un AutoLocator avec un nombre maximal de ticks défini
        from matplotlib.ticker import MaxNLocator
        ax.xaxis.set_major_locator(MaxNLocator(nbins=10))
        
        # Ajuster l'échelle pour que toutes les tâches soient visibles
        plt.xticks(rotation=45)
        
        # Visualiser les dépendances entre tâches avec des flèches
        task_id_to_index = {}
        for i, task in enumerate(tasks):
            task_id = task.get('id', f"task{i+1}")
            task_id_to_index[task_id] = i
            
        # Créer une figure en arrière-plan pour les flèches de dépendance
        for i, task in enumerate(tasks):
            predecessors = task.get('predecessors', [])
            task_start_time = mdates.date2num(datetime.strptime(task.get('start', datetime.now().strftime("%Y-%m-%d %H:%M")), "%Y-%m-%d %H:%M"))
            
            for pred in predecessors:
                if pred in task_id_to_index:
                    pred_idx = task_id_to_index[pred]
                    # Dessiner une flèche courbe entre la tâche précédente et la tâche actuelle
                    ax.annotate("",
                               xy=(task_start_time, i),  # Point d'arrivée
                               xytext=(task_start_time - 0.001, pred_idx),  # Point de départ
                               arrowprops=dict(arrowstyle="->", color="darkblue", alpha=0.7, 
                                              connectionstyle="arc3,rad=0.3"))
        
        # Ajouter les étiquettes des axes et le titre
        ax.set_yticks(range(len(tasks)))
        ax.set_yticklabels([f"{i+1}" for i in range(len(tasks))])
        ax.set_xlabel('Temps')
        ax.set_ylabel('Étape')
        ax.set_title(title, fontweight='bold', fontsize=14)
        
        # Ajouter une légende
        ax.text(0.01, 0.01, "Durée totale estimée: {} minutes".format(
                sum(task.get('duration', 0) for task in tasks)),
                transform=ax.transAxes, fontsize=10, verticalalignment='bottom',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Ajuster la disposition
        plt.tight_layout()
        
        return fig
    
    def save_gantt_visualization(self, fig, output_path=None, recipe_name=None):
        """
        Sauvegarde la visualisation du diagramme de Gantt dans un fichier image
        """
        if fig is None:
            if self.console:
                self.console.print("[red]Impossible de sauvegarder une visualisation vide[/red]")
            return None
        
        # Si aucun chemin n'est spécifié, générer un nom de fichier basé sur le nom de la recette
        if output_path is None:
            # Créer un dossier pour les visuels s'il n'existe pas
            visuals_dir = "gantt_visuals"
            os.makedirs(visuals_dir, exist_ok=True)
            
            # Générer un nom de fichier
            safe_name = "gantt"
            if recipe_name:
                safe_name = "".join([c if c.isalnum() else "_" for c in recipe_name])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"{visuals_dir}/{safe_name}_{timestamp}.png"
        
        # Sauvegarder l'image en haute qualité
        fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor(), 
                  format='png', transparent=False, pad_inches=0.2)
                  
        # Si sur un système permettant d'afficher des messages, informer l'utilisateur
        if self.console:
            self.console.print("[blue]ℹ Visualisation de diagramme de Gantt sauvegardée[/blue]")
        
        return output_path
    
    def process_gantt_file(self, json_file_path, recipe_name=None, use_ascii=True):
        """
        Traite un fichier JSON de diagramme de Gantt pour générer et sauvegarder une visualisation
        """
        # Charger les données
        gantt_data = self.load_gantt_data(json_file_path)
        
        # Extraire le nom de la recette à partir du nom de fichier si non fourni
        if recipe_name is None:
            file_name = Path(json_file_path).stem
            recipe_name = file_name.split('_')[0]
            
        # Générer les deux types de visualisation si demandé
        result = {}
        
        # Générer la visualisation ASCII
        if use_ascii:
            ascii_gantt = self.create_ascii_gantt(gantt_data, title=f"Diagramme de Gantt: {recipe_name}")
            ascii_file = self.save_ascii_gantt(ascii_gantt, recipe_name=recipe_name)
            result['ascii_file'] = ascii_file
            result['ascii_content'] = ascii_gantt
            
            # Si dans un environnement de console, afficher l'ASCII
            if self.console:
                self.console.print(ascii_gantt)
        
        # Générer la visualisation graphique si matplotlib est disponible
        if HAS_MATPLOTLIB:
            fig = self.visualize_gantt(gantt_data, title=f"Diagramme de Gantt: {recipe_name}")
            if fig:
                output_path = self.save_gantt_visualization(fig, recipe_name=recipe_name)
                result['png_file'] = output_path
        
        return result