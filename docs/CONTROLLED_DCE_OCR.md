# OCR contrôlé des DCE scannés

## Objet et périmètre

Le pipeline OCR est une capacité **locale, optionnelle et soumise à revue humaine** pour les DCE dont l’extraction native ne produit aucun fragment exploitable. Il ne remplace ni l’extraction native PDF/DOCX/XLSX, ni une validation métier, ni une validation juridique.

Le texte natif est toujours prioritaire. L’OCR n’est pas appelé pour un document qui possède déjà des fragments natifs. Les formats OCR admis dans ce lot sont `application/pdf`, `image/jpeg`, `image/png` et `image/tiff`. Les autres types restent régis par les adapters existants.

## Activation explicite

L’installation et l’activation sont indépendantes :

| Niveau | Variable | Valeur par défaut | Rôle |
|---|---|---:|---|
| Installation | `SMART_AO_INSTALL_DOCUMENT_OCR` | `0` | Ajoute l’extra `document-ocr` à l’image backend. |
| Runtime | `SMART_AO_OCR_ENABLED` | `0` | Autorise le fallback OCR dans la factory. |
| Modèle détection | `SMART_AO_OCR_DET_MODEL_PATH` | vide hors Compose | Chemin local vers le modèle ONNX de détection. |
| Modèle classification | `SMART_AO_OCR_CLS_MODEL_PATH` | vide hors Compose | Chemin local vers le modèle ONNX de classification. |
| Modèle reconnaissance | `SMART_AO_OCR_REC_MODEL_PATH` | vide hors Compose | Chemin local vers le modèle ONNX de reconnaissance. |
| Dictionnaire | `SMART_AO_OCR_REC_KEYS_PATH` | vide hors Compose | Fichier local du dictionnaire de caractères. |
| Rendu PDF | `SMART_AO_OCR_DPI` | `150` | Résolution bornée entre 72 et 300 DPI. |

L’activation runtime sans les trois modèles et le dictionnaire local existants produit `FAILED_SAFE` avec `OCR_MODELS_REQUIRED` ou `OCR_RUNTIME_UNAVAILABLE`. Le code ne fournit jamais de répertoire de cache à RapidOCR et passe explicitement le dictionnaire local : aucun téléchargement automatique de modèle ou de dictionnaire n’est autorisé par ce pipeline.

## Limites et comportement terminal

Le rendu est limité à 200 pages OCR, 25 millions de pixels par page et 250 millions de pixels au total. Les dépassements produisent `REJECTED_LIMIT` avec `OCR_EXTRACTION_LIMIT`, sans fragments partiels. Une erreur d’initialisation ou d’inférence produit `FAILED_SAFE` avec un code borné. Une sortie vide produit `FAILED_SAFE` avec `OCR_EMPTY_TEXT`.

Lorsqu’un texte OCR est produit, l’extraction est enregistrée en `REVIEW_REQUIRED` avec `OCR_HUMAN_REVIEW_REQUIRED`. Les fragments sont conservés parce qu’ils sont utiles à la revue, mais ce statut interdit de considérer la projection comme une preuve validée. Les statuts et la contrainte SQL sont versionnés par la migration Alembic `20260826_0067`.

## Provenance et confidentialité

Chaque fragment OCR porte un locator `ocr_page` avec la page et l’ordre de lecture. Une bbox quadrilatère n’est ajoutée que si les quatre points sont finis et dans les dimensions de l’image. Les fragments restent bornés par les limites communes de fragmentation et reçoivent un hash SHA-256. Le document original n’est pas copié dans la commande, l’événement ou la sortie du worker.

L’identifiant d’extracteur `smart-ao-rapidocr` et sa version sont inclus dans l’identité idempotente de l’extraction. Une extraction native et une extraction OCR ne se confondent donc pas dans la contrainte d’unicité. L’isolation tenant et les contrôles d’intégrité de l’objet consommé restent ceux du service d’extraction existant.

## Dépendances et exploitation

L’extra `document-ocr` déclare RapidOCR et ONNX Runtime. Les fichiers ONNX doivent être préchargés dans un volume privé et monté en lecture seule par l’opérateur. Le lot ne télécharge pas de modèles, ne contacte pas de fournisseur externe et ne fournit pas de modèle par défaut. L’absence du binaire Tesseract n’est pas contournée ni masquée : ce lot utilise uniquement le chemin RapidOCR/ONNX explicitement déclaré.

Le worker DCE existant est déjà le point d’exécution approprié : il appelle la factory puis le service d’extraction et n’imprime aucun fragment. Aucun endpoint public ne permet d’activer l’OCR ou de fournir un chemin de modèle.

## Ce que ce lot ne prouve pas

Aucune précision, aucun rappel, aucune mesure CER/WER et aucune performance métier ne sont déclarés. Aucun corpus DCE réel n’a été utilisé : les tests reposent sur des fixtures synthétiques contrôlées et un moteur simulé. Une recette avec corpus autorisé, modèles identifiés, seuils, échantillonnage et validation humaine reste à conduire hors de ce lot. L’OCR ne constitue pas une décision juridique et ne publie aucune clause sans revue humaine.
