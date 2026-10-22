# Étape 1 — Matériel, NAND et récupération autorisée du mot de passe

## But

Établir une base matérielle fiable avant toute modification du logiciel : identifier les composants, réaliser une sauvegarde NAND stable et conserver les informations sensibles hors Git.

## Matériel identifié

| Élément | Identification |
| --- | --- |
| Carte | `TPP06-Z-AK V1.0.2` |
| Processeur | Anyka `AK3761EE128` |
| NAND | GigaDevice `GD5F1GM7UEYIG` |
| Boîtier NAND | WSON-8 / QFN-8, 8 × 6 mm, 3,3 V |
| Programmateur | XGecu T48 avec adaptateur QFN/WSON-8 8 × 6 mm |

![Programmateur T48](../../media/lecture-nand/01-programmateur-t48.jpg)

## Ordre conseillé

1. Essayer d’abord la [liste publique de candidats non vérifiés](candidats-mot-de-passe.md) via l’accès local/UART autorisé.
2. Si elle ne donne aucun accès, lire la NAND au XGecu afin de créer une sauvegarde puis d’analyser le système.

## Lecture NAND

1. Débrancher le panneau et le T48 avant chaque manipulation.
2. Lire la puce hors carte avec l’adaptateur 8 × 6 mm.
3. Vérifier l’identifiant avant la lecture.
4. Réaliser plusieurs lectures et comparer les fichiers localement.
5. Ne jamais utiliser `Erase` ni `Program` pour faire une sauvegarde.
6. Ressouder la puce avec le repère de broche 1 dans le bon coin, puis valider le démarrage.

![Lecture vérifiée dans XGPro](../../media/lecture-nand/10-lecture-verifiee.png)

La sauvegarde binaire reste privée et hors GitHub.

## Recherche autorisée du mot de passe

Sur les deux panneaux observés, le hash pertinent a été trouvé en cherchant `root:` ou `root` dans le dump NAND brut. Le hash MD5crypt commençant par `$1$`, trouvé dans SquashFS, n’était pas le bon indice pour cette méthode.

Cette observation ne garantit pas le même résultat sur toute autre carte. Une [liste de candidats non vérifiés](candidats-mot-de-passe.md) est publiée à des fins de test autorisé ; ne publiez pas le hash, le dump, les clés ou les identifiants propres à un appareil.

## Sortie de l’étape

- Sauvegarde NAND locale validée.
- Panneau remonté et démarré.
- Dumps, hashes et identifiants propres à un appareil conservés dans un emplacement privé.
