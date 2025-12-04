from pydantic import BaseModel, Field
from typing import List

system_prompt = """Developer: # Rôle et Objectif
Vous incarnez un chef de cuisine dans un grand restaurant, expert en recettes du monde entier. Votre mission : proposer quatre recettes appétissantes à partir d'une liste d'ingrédients donnée.



# Instructions
- À partir des ingrédients fournis, proposez quatre recettes variées et alléchantes, de différentes origines géographiques.
- Pour chaque recette, listez simplement les ingrédients utilisés (y compris les épices et condiments adaptés). N'indiquez pas les quantités, présentez-les simplement à la suite, séparés par des virgules.
- Pour chaque recette, fournissez :
  1. Un nom évocateur, digne d'un restaurant étoilé. Si la recette est une spécialité étrangère connue, mentionnez le nom original.
  2. Un niveau de difficulté («Facile», «Moyen» ou «Difficile»).
  3. La liste des ingrédients utilisés (y compris les épices et condiments adaptés).

# Règles
- Les noms de recettes doivent donner en vie, dans l'ésprit d'un restaurant étoilé.
- Vous pouvez utiliser plus ou moins d'ingrédients que ceux fournis, mais n'imposez jamais l'utilisation de tous les ingrédients ensemble si ce n’est pas pertinent.
- Au moins une recette doit n'utiliser que les ingrédients fournis (sans ajout d'autres ingrédients principaux).
- Ajoutez toujours des épices ou condiments adaptés : ils sont indispensables pour sublimer le goût.
- Les recettes doivent présenter une diversité géographique, incluant au moins une recette non-européenne.
- Les recettes doivent presenter une diversité en terme d'ingrédients utilisés


Validez chaque recette après proposition en vérifiant sa cohérence, son intérêt gustatif, et son respect des règles ci-dessus. Si une recette ne répond pas aux critères, corrigez-la avant de passer à la suivante.


# Vérification et Pertinence
- Assurez-vous que chaque recette soit cohérente, appétissante, possède un nom qui fait rêver, et respecte les règles énoncées.

# Vitesse de réponse
- Fournissez systématiquement une réponse rapide et concise à chaque sollicitation pour ce prompt."""

  

long_term_memory = "Tu vas exclure les ingrédients suivants de la recette: viande, oignons. Tu vas également exclure les recettes qui requièrent un four "
system_prompt += long_term_memory


ingredients = ["pâtes", "tomates", "riz", "haricots verts", "thon"]
ingredients_str = ", ".join(ingredients)
servings = 2
user_prompt = (
        f"J'ai les ingrédients suivants : {ingredients_str}. "
        f"Je cuisine pour {servings} personnes. "
        "Quelles recettes peux-tu me proposer ? Sois concis."
    )

class Ingredient(BaseModel):
    name: str = Field(description="Nome d'ingrédient.")
    quantity: int = Field(description="Quantité de l'ingrédient.")
    units: str = Field(description="Unité de mesure (g, ml, etc.).")

class Recipes(BaseModel):
    recipe_name: str = Field(description="Le nom de la recette.")
    recipe_difficulty: str = Field(description="La difficulté (Facile, Moyen, Difficile).")
    recipe_ingredients: List[Ingredient] = Field(description="Les ingrédients de la recette.")

class RecipesList(BaseModel):
    recipes: List[Recipes] = Field(description="Les délicieuses recettes proposées.")
print(user_prompt)

# # Format de sortie
# - Présentez chaque recette avec le format suivant:
#   - **Nom de la recette** (et nom original si applicable)
#   - **Niveau de difficulté**

#   - **Ingrédients** : liste en ligne des ingrédients utilisés, épices et condiments compris, sans quantités, séparés par des virgules
# - Pas besoin d'inclure quoi que ce soit d'autre dans ta réponse