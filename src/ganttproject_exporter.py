import os
import json
from datetime import datetime, timedelta
import xml.dom.minidom as md
import uuid


class GanttProjectExporter:
    """
    Classe pour exporter les données de diagramme Gantt au format GanttProject (.gan)
    """
    
    def __init__(self, console=None):
        self.console = console
    
    def load_json_data(self, json_file_path):
        """
        Charger les données JSON du diagramme Gantt
        """
        with open(json_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def export_to_ganttproject(self, gantt_data, recipe_name=None, output_path=None):
        """
        Exporte les données du diagramme Gantt au format .gan (XML) compatible avec GanttProject
        """
        # Créer un nouveau document XML
        doc = md.getDOMImplementation().createDocument(None, "project", None)
        project = doc.documentElement
        
        # Ajouter les attributs du projet
        project.setAttribute("name", recipe_name or "Recette")
        project.setAttribute("company", "Robotatouille")
        project.setAttribute("webLink", "")
        project.setAttribute("view-date", datetime.now().strftime("%Y-%m-%d"))
        project.setAttribute("version", "3.2.3230")
        project.setAttribute("view-index", "0")
        
        # Ajouter des informations de description
        desc = doc.createElement("description")
        desc_text = doc.createTextNode(f"Diagramme de Gantt pour la recette: {recipe_name}")
        desc.appendChild(desc_text)
        project.appendChild(desc)
        
        # Créer une date de début de projet (aujourd'hui)
        today = datetime.now()
        start_date = today.replace(hour=8, minute=0, second=0, microsecond=0)  # Début à 8h du matin
        
        # Configurer les tâches
        tasks = doc.createElement("tasks")
        project.appendChild(tasks)
        
        # Mapper les IDs des tâches JSON aux IDs GanttProject
        task_id_mapping = {}
        
        # Créer les tâches
        for i, task_data in enumerate(gantt_data.get('tasks', [])):
            # Générer un ID unique pour GanttProject (nécessaire car GanttProject utilise des entiers)
            gp_task_id = i + 1
            task_id_mapping[task_data.get('id', str(i+1))] = gp_task_id
            
            # Créer l'élément de tâche
            task = doc.createElement("task")
            task.setAttribute("id", str(gp_task_id))
            task.setAttribute("name", task_data.get('name', f"Tâche {i+1}"))
            
            # Calculer les dates
            duration_minutes = task_data.get('duration', 0)
            task_start_str = task_data.get('start', start_date.strftime("%Y-%m-%d %H:%M"))
            
            try:
                task_start = datetime.strptime(task_start_str, "%Y-%m-%d %H:%M")
            except ValueError:
                # Utiliser la date du jour par défaut
                task_start = start_date + timedelta(minutes=i*5)  # Décaler les tâches de 5 minutes
            
            # Convertir la date de début au format GanttProject (jours depuis le 1/1/1970)
            start_date_epoch = datetime(1970, 1, 1)
            days_since_epoch = (task_start - start_date_epoch).days
            
            task.setAttribute("start", str(days_since_epoch))
            task.setAttribute("duration", str(duration_minutes / (60 * 8)))  # Durée en jours de travail (8h)
            task.setAttribute("complete", "0")  # 0% terminé par défaut
            task.setAttribute("expand", "true")
            task.setAttribute("cost-manual-value", "0.0")
            task.setAttribute("cost-calculated", "false")
            
            # Ajouter la tâche à la liste des tâches
            tasks.appendChild(task)
        
        # Ajouter les dépendances entre tâches
        for i, task_data in enumerate(gantt_data.get('tasks', [])):
            task_id = task_data.get('id', str(i+1))
            if task_id in task_id_mapping:
                gp_task_id = task_id_mapping[task_id]
                
                # Récupérer les prédécesseurs
                predecessors = task_data.get('predecessors', [])
                
                for pred in predecessors:
                    if pred in task_id_mapping:
                        gp_pred_id = task_id_mapping[pred]
                        
                        # Créer une relation de dépendance
                        task = doc.getElementsByTagName("task")[i]  # Récupérer la tâche correspondante
                        
                        depend = doc.createElement("depend")
                        depend.setAttribute("id", str(gp_pred_id))
                        depend.setAttribute("type", "2")  # Type 2 = Finish-to-Start
                        depend.setAttribute("difference", "0")
                        depend.setAttribute("hardness", "Strong")
                        
                        task.appendChild(depend)
        
        # Ajouter des ressources (vide, mais nécessaire pour la structure)
        resources = doc.createElement("resources")
        project.appendChild(resources)
        
        # Ajouter des allocations (vide, mais nécessaire pour la structure)
        allocations = doc.createElement("allocations")
        project.appendChild(allocations)
        
        # Ajouter des jours fériés (vide, mais nécessaire pour la structure)
        vacations = doc.createElement("vacations")
        project.appendChild(vacations)
        
        # Définir le chemin de sortie si non spécifié
        if output_path is None:
            # Créer un dossier pour les fichiers GanttProject
            gan_dir = "gantt_files"
            os.makedirs(gan_dir, exist_ok=True)
            
            # Générer un nom de fichier
            safe_name = "".join([c if c.isalnum() else "_" for c in (recipe_name or "recette")])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"{gan_dir}/{safe_name}_{timestamp}.gan"
        
        # Écrire le document XML dans un fichier .gan
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(doc.toprettyxml(indent="  "))
            
        # Message de console supprimé (l'information est déjà affichée dans le panneau Planification)
        
        return output_path
