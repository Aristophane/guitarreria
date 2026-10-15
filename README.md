# Guitarreria

Site : https://aristophane.github.io/guitarreria/

Le dossier `dist` contient le site complet et les photographies originales.
Les liens internes sont relatifs, pour fonctionner sous le chemin GitHub Pages
du dépôt. Les photos et les textes conservent leurs droits d'origine.

## Publication

Chaque envoi sur `main` publie `dist` avec le workflow GitHub Pages.
La configuration du dépôt doit utiliser GitHub Actions comme source de Pages.

## Reconstruction

Avec Python et `lxml` installés :

```sh
python scripts/build_site.py
```

`source` conserve les documents originaux, les styles et les données des luthiers.
`site-config.json` définit l'adresse utilisée par les URL canoniques et le sitemap.
Le site fonctionne sans serveur applicatif ni connexion à ChatGPT Sites.
