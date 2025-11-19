import json
import os
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta


class PlotlyGanttVisualizer:
    """
    Classe pour visualiser les diagrammes de Gantt à l'aide de Plotly Express
    """
    
    def __init__(self, console=None):
        self.console = console
    
    def load_gantt_data(self, json_file_path):
        """
        Charge les données du diagramme de Gantt à partir d'un fichier JSON
        """
        with open(json_file_path, 'r', encoding='utf-8') as f:
            gantt_data = json.load(f)
        return gantt_data
    
    def create_dataframe(self, gantt_data, recipe_name=None):
        """
        Convertit les données Gantt en DataFrame Pandas pour Plotly
        """
        tasks_data = gantt_data.get('tasks', [])
        if not tasks_data:
            if self.console:
                self.console.print("[red]Aucune tâche trouvée dans les données du diagramme de Gantt[/red]")
            return pd.DataFrame()
        
        # Pour chaque étape, déterminer ses prédécesseurs
        task_id_to_name = {task.get('id', f"task{i}"): task.get('name', f"Tâche {i}") 
                          for i, task in enumerate(tasks_data)}
        
        # Créer les données pour le DataFrame
        df_data = []
        
        for task in tasks_data:
            task_id = task.get('id')
            task_name = task.get('name')
            
            # Calculer les dates de début et de fin
            try:
                start_str = task.get('start')
                start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
                
                duration_minutes = task.get('duration', 0)
                finish_time = start_time + timedelta(minutes=duration_minutes)
                
                # Récupérer les dépendances
                predecessors = task.get('predecessors', [])
                predecessor_names = [task_id_to_name.get(pred_id, pred_id) for pred_id in predecessors]
                dependencies = ', '.join(predecessor_names) if predecessor_names else "Aucune"
                
                # Ajouter les données pour cette tâche
                df_data.append({
                    'Task': task_name,
                    'ID': task_id,
                    'Start': start_time,
                    'Finish': finish_time,
                    'Duration': duration_minutes,
                    'Dependencies': dependencies
                })
            except Exception as e:
                if self.console:
                    self.console.print(f"[yellow]Erreur lors du traitement de la tâche {task_id}: {str(e)}[/yellow]")
        
        # Créer le DataFrame
        if df_data:
            return pd.DataFrame(df_data)
        else:
            return pd.DataFrame()
    
    def create_gantt_figure(self, df, recipe_name=None):
        """
        Crée une figure Gantt Plotly à partir du DataFrame
        """
        if df.empty:
            if self.console:
                self.console.print("[red]Impossible de créer un diagramme Gantt avec des données vides[/red]")
            return None
        
        title = f"Diagramme de Gantt: {recipe_name}" if recipe_name else "Diagramme de Gantt"
        
        # Créer la figure avec Plotly Express
        fig = px.timeline(
            df, 
            x_start="Start", 
            x_end="Finish", 
            y="Task",
            color="Task",  # Colorer par tâche
            hover_data=["Duration", "Dependencies"],  # Données supplémentaires au survol
            labels={"Task": "Tâche", "Duration": "Durée (min)", "Dependencies": "Dépendances"},
            title=title
        )
        
        # Configuration supplémentaire de la figure
        fig.update_layout(
            xaxis_title="Temps",
            yaxis_title="Étapes de cuisine",
            height=max(600, len(df) * 40),  # Hauteur adaptative selon le nombre de tâches
            font=dict(family="Arial", size=12),
            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
            margin=dict(l=150, r=50, t=80, b=50),
            showlegend=False  # Supprimer la légende qui est redondante avec les titres des étapes
        )
        
        # Ajuster les yaxis pour que les étapes soient dans l'ordre inverse (première en haut)
        fig.update_yaxes(autorange="reversed")
        
        # Ajouter des lignes verticales pour les dépendances
        for i, row in df.iterrows():
            if row['Dependencies'] != "Aucune":
                task_name = row['Task']
                task_start = row['Start']
                
                # Parcourir les dépendances de cette tâche pour ajouter des connecteurs
                for dep_name in row['Dependencies'].split(', '):
                    # Trouver la tâche de dépendance dans le DataFrame
                    dep_rows = df[df['Task'] == dep_name]
                    if not dep_rows.empty:
                        dep_row = dep_rows.iloc[0]
                        dep_end = dep_row['Finish']
                        
                        # Ajouter une annotation pour montrer la dépendance
                        fig.add_shape(
                            type="line",
                            x0=dep_end,
                            y0=dep_row['Task'],
                            x1=task_start,
                            y1=task_name,
                            line=dict(color="gray", width=1, dash="dot"),
                            layer="below"
                        )
        
        return fig
    
    def save_html_gantt(self, fig, output_path=None, recipe_name=None):
        """
        Sauvegarde le diagramme de Gantt au format HTML interactif
        """
        if fig is None:
            if self.console:
                self.console.print("[red]Impossible de sauvegarder une figure vide[/red]")
            return None
        
        # Si aucun chemin n'est spécifié, générer un nom de fichier
        if output_path is None:
            # Créer un dossier pour les visualisations HTML s'il n'existe pas
            html_dir = "gantt_html"
            os.makedirs(html_dir, exist_ok=True)
            
            # Générer un nom de fichier
            safe_name = "".join([c if c.isalnum() else "_" for c in (recipe_name or "recette")])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"{html_dir}/{safe_name}_{timestamp}.html"
        
        # Sauvegarder en HTML interactif
        fig.write_html(output_path, include_plotlyjs=True, full_html=True)
        
        if self.console:
            self.console.print(f"[green]✓ Diagramme de Gantt interactif sauvegardé: {output_path}[/green]")
        
        return output_path
    
    def process_gantt_file(self, json_file_path, recipe_name=None):
        """
        Traite un fichier JSON de diagramme de Gantt pour générer une visualisation Plotly
        """
        # Charger les données
        gantt_data = self.load_gantt_data(json_file_path)
        
        # Extraire le nom de la recette à partir du nom de fichier si non fourni
        if recipe_name is None:
            import os.path
            file_name = os.path.basename(json_file_path)
            recipe_name = file_name.split('_')[0]
        
        # Convertir en DataFrame
        df = self.create_dataframe(gantt_data, recipe_name)
        
        # Créer la figure
        fig = self.create_gantt_figure(df, recipe_name)
        
        # Sauvegarder en HTML
        html_path = self.save_html_gantt(fig, recipe_name=recipe_name)
        
        return {
            'html_file': html_path,
            'figure': fig
        }
