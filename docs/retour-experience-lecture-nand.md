# Retour d’expérience : lecture NAND et recherche du hash de mot de passe

> Ce retour porte sur deux panneaux MOES / Tuya TPP06 équipés d’une NAND GigaDevice. Il décrit une méthode qui a fonctionné sur ces deux appareils ; il ne garantit pas que toutes les cartes ont le même agencement ou les mêmes identifiants.

## Lecture de la NAND

La lecture sur carte avec des pointes pogo n’a pas fonctionné dans ce cas. La puce a donc été dessoudée à l’air chaud, lue avec un XGecu T48 et un adaptateur adapté, puis ressoudée sur la carte.

Laisser la carte chauffer uniformément avant de soulever la puce. Une station à air chaud réglée à **350 °C** a été utilisée sur ces deux panneaux. La température et le débit d’air adaptés dépendent de la station, de la buse et de la carte ; ne pas faire levier sous le boîtier.

## Recherche du hash de mot de passe

Lors de l’extraction des partitions SquashFS, un hash MD5crypt commençant par `$1$` a été trouvé. Il semble ne pas correspondre à la méthode de récupération du mot de passe root recherchée.

Sur ces deux panneaux, le hash DEScrypt pertinent a été trouvé en recherchant directement `root:` ou `root` dans le **dump NAND brut produit par XGPro**, sans commencer par extraire les partitions.

Ne pas publier le dump brut, le hash, le mot de passe obtenu, les identifiants de l’appareil ou les clés. Les conserver uniquement dans un stockage local protégé.
