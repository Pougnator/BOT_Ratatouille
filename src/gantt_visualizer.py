import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import json
from datetime import datetime, timedelta
import os
from pathlib import Path


class GanttVisualizer:
    """
    Classe pour visualiser les diagrammes de Gantt générés par l'application
    """
    
    def __init__(self, console=None):
        self.console = console
        # Utiliser un style agréable pour les graphiques
        plt.style.use('ggplot')
    
    def load_gantt_data(self, json_file_path):
        """
        Charge les données du diagramme de Gantt à partir d'un fichier JSON
        """
        with open(json_file_path, 'r', encoding='utf-8') as f:
            gantt_data = json.load(f)
        return gantt_data
    
    def visualize_gantt(self, gantt_data, title="Diagramme de Gantt de la recette"):
        """
        Visualise un diagramme de Gantt à partir des données
        """
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
    
    def process_gantt_file(self, json_file_path, recipe_name=None):
        """
        Traite un fichier JSON de diagramme de Gantt pour générer et sauvegarder une visualisation
        """
        # Charger les données
        gantt_data = self.load_gantt_data(json_file_path)
        
        # Extraire le nom de la recette à partir du nom de fichier si non fourni
        if recipe_name is None:
            file_name = Path(json_file_path).stem
            recipe_name = file_name.split('_')[0]
        
        # Visualiser
        fig = self.visualize_gantt(gantt_data, title=f"Diagramme de Gantt: {recipe_name}")
        
        # Sauvegarder et retourner le chemin du fichier
        output_path = self.save_gantt_visualization(fig, recipe_name=recipe_name)
        
        return output_path
