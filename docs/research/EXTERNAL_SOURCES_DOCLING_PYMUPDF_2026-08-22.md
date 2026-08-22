# Sources vérifiées — Docling et PyMuPDF — 22 août 2026

## Docling

Source officielle : [Docling Quickstart](https://docling-project.github.io/docling/getting_started/quickstart/)

Le quickstart officiel montre l’API Python `from docling.document_converter import DocumentConverter`, puis `converter.convert(source).document` et `doc.export_to_markdown()`.

Source officielle complémentaire : [dépôt Docling](https://github.com/docling-project/docling)

Le dépôt officiel indique que Docling prend en charge plusieurs formats, notamment PDF, DOCX, PPTX, XLSX et images, avec une représentation `DoclingDocument`, des exportations Markdown/HTML/JSON et une exécution locale adaptée aux environnements sensibles ou isolés. Docling dispose également d’un support OCR, mais son exécution et ses modèles doivent être bornés séparément.

## PyMuPDF

Source officielle : [PyMuPDF — Text recipes](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)

La documentation officielle décrit `pymupdf.open(stream=..., filetype="pdf")`, puis `page.get_text("blocks", sort=True)` pour obtenir des blocs de texte avec positions. Elle précise que l’ordre du texte PDF peut être imparfait et que les blocs/localisateurs peuvent servir à reconstruire un ordre de lecture.

## Décision d’intégration

Le slice ajoute un port d’extraction avancée et deux adaptateurs optionnels : PyMuPDF pour les blocs PDF localisés et Docling pour les formats complexes. Aucun modèle ou téléchargement n’est déclenché à l’import. Le fallback actuel `pypdf`/DOCX/XLSX reste la source déterministe par défaut, et toute sortie avancée doit rester candidate à revue humaine avec statut et provenance explicites.
