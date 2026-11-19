# Bip tactile : correctif confirmé sur le panneau de référence

État au 19 novembre 2026 : après installation de `0.1.6-buzzer.1`, le
propriétaire confirme le fonctionnement du bip. Le binaire installé et
l'API chiffrée ont été vérifiés. Cela valide le clic sur ce panneau, pas toutes
les variantes matérielles ni la durée électrique exacte.

Historique : la V6 initiale affichait correctement la météo, mais le premier
appui tactile mettait le pilote sonore en défaut. La lecture après échec
montrait les deux sélections à zéro et le PWM désactivé/non demandé.

Le correctif `0.1.6-buzzer.1` reprend l'ordre des écritures Tuya : période
d'abord si elle dépasse l'ancien rapport cyclique, sinon rapport cyclique
d'abord. L'ancien code écrivait un rapport de zéro avant la période ; Linux
4.4 refuse cette écriture lorsque la période vaut zéro. Un test simulant cette
contrainte reproduit le défaut et couvre le correctif ainsi que l'état conservé
entre deux exports. C'est un défaut confirmé du code, pas encore la preuve que
c'est l'unique cause sur le panneau. Les erreurs indiquent désormais l'étape,
le chemin et `errno`. Le propriétaire a confirmé le résultat sonore du correctif.

Référence noyau : [`duty_cycle_store` transmet la période courante à
`pwm_config`](https://github.com/torvalds/linux/blob/v4.4/drivers/pwm/sysfs.c),
qui [rejette une période nulle](https://github.com/torvalds/linux/blob/v4.4/drivers/pwm/core.c).

## Réglage V6 préparé

Dans **Menu → Paramètres → Bip au toucher**, le réglage commande réellement le
pilote local et est aussi exposé dans HA. À la demande du propriétaire,
`RESTORE_DEFAULT_ON` active la préférence par défaut et conserve ensuite son
choix, y compris OFF. Aucun son de démarrage n'est demandé : les sons viennent
uniquement d'un nouvel appui tactile, pas de ses mouvements. La conservation
après coupure réelle reste à vérifier sur le panneau.

Le pilote n'écrit rien au démarrage. Il vérifie le profil matériel, refuse un
PWM déjà exporté ou un programme Tuya concurrent, et prend un verrou local.
Une tâche séparée réalise chaque bip ; aucune file d'attente et au moins 200 ms
entre demandes. Désactiver le réglage demande l'annulation, contrôlée entre les
attentes de 0,5 ms. L'arrêt PWM et le retour des deux sélections à zéro sont
tentés même après erreur ; le pilote se verrouille en défaut si l'opération échoue.

Les tests simulés couvrent lecture de la préférence dans le YAML, configuration
ESPHome/génération C++, succès, annulation et échecs de transaction. Une
compilation native de contrôle du pilote et une compilation ARM du firmware
passent. Le premier build ARM a détecté un `override` de destructeur invalide ;
il a été corrigé et le test natif utilise désormais la même contrainte que la
classe ESPHome. Cela ne remplace pas la validation sonore sur le panneau.

**Limite matérielle :** un SIGKILL, une panne noyau ou une écriture sysfs bloquée
peut empêcher le nettoyage. La durée demandée n'est pas une garantie temps réel.
Un essai sonore supervisé et la validation sur la cible restent nécessaires
avant déploiement ; le secours multiboot ne constitue pas un arrêt PWM garanti.

## Résultats

La bibliothèque `libtuya_app.so` analysée a pour SHA-256
`f940aeee4a70e6ccb7f12eda075b40c7a3577484f1a460c327d9055d5d8477f7`.
Elle n'est pas distribuée par ce dépôt. Les adresses ci-dessous sont relatives
à cette bibliothèque précise, pas des adresses à appeler sur le panneau.

| Élément | Observation |
| --- | --- |
| Enregistrement du clic | `tuya_buzzer_init` à `0x2c27ec` enregistre le callback `0x2c23e8` via `lv_event_add_all_clicked_cb` |
| Réglage sonore | Le callback vérifie `gui_ctrl_click_sound_switch` et le mode muet avant de demander un son |
| Limitation | `0x2c2280` limite les demandes à un intervalle d'au moins 200 ms |
| Travail sonore | Le callback lance `0x2c21ec` dans le pool de threads, pas dans la boucle graphique |
| Sorties | `BUZ_EN1` = GPIO 8, `BUZ_EN2` = GPIO 18, actives à l'état haut |
| Sélection du clic | Mode 1 du sélecteur `0x2c1c28` : `BUZ_EN1=0`, `BUZ_EN2=1` |
| Générateur | PWM matériel `pwm1`, `pwmchip1`, canal `pwm0`, distinct des relais |
| Tonalité du clic | 4 750 Hz ; période 210 526 ns ; rapport cyclique proche de 50 % (105 250 ns avec l'arrondi entier Tuya) |
| Durée demandée | 4 000 µs, puis désactivation PWM ; durée réelle non mesurée |

La routine `0x2c1ef4` écrit la période et le rapport cyclique, active le PWM,
attend via `select`, puis le désactive. Elle adapte l'ordre des écritures de
période/rapport cyclique au rapport cyclique précédent (initialement zéro).
Le portage lit l'état sysfs réel après export, avec PWM désactivé, au lieu de
supposer cet état. Ce n'est pas une simple
impulsion sur un GPIO, ni un fichier audio à jouer sur un haut-parleur.

## État matériel lu

Le noyau de référence est `4.4.192V2.4`, architecture `armv5tejl`. Les deux
sorties `BUZ_EN` étaient à zéro, en direction `out`, avec `active_low=0`.
L'arbre matériel confirme les GPIO 8 et 18 et leur valeur initiale zéro.
`pwmchip1` existe et déclare un canal ; son sous-répertoire `pwm0` n'était pas
exporté lors de l'inventaire. L'application ESPHome était saine.

L'absence du canal sysfs exporté ne prouve pas à elle seule l'état électrique
du PWM. Ne pas exporter ou activer des canaux au hasard, ni réutiliser les
routines de test usine, ni appeler directement la bibliothèque Tuya.

## Avant intégration

1. Vérifier l'identité du contrôleur, les broches, la polarité et l'absence de
   propriétaire concurrent sur le matériel cible.
2. Vérifier sur la cible le pilote préparé, avec durée bornée, arrêt PWM et
   restauration des sélections sur erreur/arrêt ordonné. Une fermeture de
   fichier sysfs n'arrête pas nécessairement un PWM matériel.
3. Tester les erreurs et le nettoyage en simulation. Ne pas bloquer LVGL ni
   les commandes des relais pendant le bip.
4. Faire un unique essai bref, supervisé par une personne pouvant écouter et
   intervenir, puis vérifier le retour à l'état silencieux et les accès réseau.
5. Seulement après validation, relier les clics LVGL au réglage local
   « Bip au toucher ». Une désactivation doit interrompre aussi un son actif.

Une analyse statique n'est pas une validation acoustique ni une garantie de
compatibilité entre toutes les variantes. La météo est indépendante du pilote
sonore et ne nécessite aucun accès GPIO.
