# Récupération du mot de passe

Cette partie concerne uniquement l’appareil dont le propriétaire a autorisé la maintenance.

## Pré-requis

1. Une sauvegarde NAND lue et vérifiée hors Git.
2. Une console UART câblée sans alimentation injectée par l’adaptateur USB–UART.
3. Un espace local protégé pour conserver tout secret récupéré.

## Règles de conservation

- Ne jamais committer le dump NAND.
- Ne jamais committer un mot de passe, une clé privée, un jeton, un numéro de série ou une clé ADB.
- Conserver les secrets uniquement dans un gestionnaire de mots de passe ou une note chiffrée locale.
- Dans ce dépôt, ne documenter que la méthode, l’état d’avancement et les éléments non sensibles.

## État

La sauvegarde est validée et le démarrage du panneau est confirmé. La connexion UART et la récupération autorisée du mot de passe restent à documenter sans publier de secret.
