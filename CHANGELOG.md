# Changelog

Toutes les modifications notables d'**APK Tool GUI Linux** sont listées ici.
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [SemVer](https://semver.org/lang/fr/).

## [1.0.2] - 2026-11-21

### Ajouté
- Interface en **espagnol** et en **russe**, en plus du français et de l'anglais (choix dans *Paramètres → Langue*, ou langue du système par défaut).
- Actions du clic droit Nemo et raccourci du menu traduits dans les 4 langues.
- Boutons standard (OK/Annuler, Oui/Non) traduits ; textes des dialogues Qt traduits si le paquet `qt6-translations-l10n` est installé (recommandé par le .deb).
- La boîte « À propos » est traduite et affiche la version d'Apktool intégrée.

### Modifié
- **Apktool 3.0.2 → 3.0.3** : correction des erreurs « android:* not found », valeurs de flags vides acceptées, pool de chaînes optimisé. Options en ligne de commande inchangées.
- **APKEditor 1.4.7 → 1.4.9** : correction d'un bug de fusion des split APK, gestion des registres « wide » en smali, meilleures performances.
- La fenêtre s'élargit si besoin pour que les 9 onglets restent visibles (russe).

### Corrigé
- La ligne « Picked up _JAVA_OPTIONS… » s'affichait à la place de la version d'APKEditor quand la variable `_JAVA_OPTIONS` est définie (courant sous Linux pour le lissage des polices Java). Ces lignes sont maintenant filtrées partout.
- Boutons d'action tronqués quand le texte est long (onglet Baksmali en russe).

## [1.0.1] - 2026-10-28

### Corrigé
- **Icône absente dans l'onglet Infos APK** pour les applis récentes (ex. AnyDesk) qui déclarent une icône adaptative XML (`mipmap-anydpi-v26`) avec des noms de ressources raccourcis ou obfusqués.

### Ajouté
- Nouveau moteur d'extraction d'icône (`icon.py`) basé sur les ID de ressources (`aapt2 dump resources` / `dump xmltree`) :
  - récupère le PNG/WebP d'origine en plus haute densité caché derrière l'icône adaptative ;
  - sinon, rendu de l'icône adaptative : fond, premier plan, VectorDrawable (groupes, transformations, clip-path), `inset`, `layer-list`, `bitmap`, `shape`, dégradés linéaires/radiaux, masque à coins arrondis ;
  - lecture de l'icône déclarée dans l'AndroidManifest en dernier recours ;
  - fonctionne aussi quand les noms d'attributs et de ressources sont obfusqués (R8, AndResGuard, `--shorten-resource-paths`).
- Conversion WebP → PNG de secours via Pillow si le plugin WebP de Qt est absent.

### Modifié
- Nouvelles dépendances du paquet : `python3-pyqt6.qtsvg`, `qt6-image-formats-plugins`.

## [1.0.0] - 2026-10-19

Première version : portage Linux natif (Python 3 + PyQt6) d'[APKToolGUI](https://github.com/AndnixSH/APKToolGUI) 3.4.0.0 d'AndnixSH.

### Ajouté
- Les 9 onglets de l'original : Principal, Infos APK, Décodage, Build, Signer, Zipalign, Framework, Baksmali, ADB.
- Outils intégrés : Apktool 3.0.2, APKEditor 1.4.7, apksigner, smali/baksmali, aapt2 Linux.
- Décompilation/compilation Apktool ou APKEditor (projet APKEditor détecté automatiquement).
- Fusion XAPK/APKS/APKM/ZIP et décompilation directe des split APK.
- Chaîne compiler → zipalign → signer → installer ADB ; APK non signé avec la signature d'origine.
- Correctifs Apktool automatiques (manifest, `sparseResources`, `APKTOOL_DUMMY`).
- Signature par clé pem/pk8 ou keystore JKS, schémas v1 à v4 ; mots de passe transmis par variable d'environnement.
- Options adaptées à Apktool 3 (`-a`, `--no-assets`, `--only-manifest`, `--debuggable`, tag de framework).
- Onglet ADB : liste des appareils, connexion Wi-Fi `IP:port`, installation (`-i com.android.vending`, `--abi`).
- Actions de clic droit dans Nemo (Linux Mint) installées pour tout le système.
- Ligne de commande : `--decompile`, `--compile`, `--sign`, `--align`, `--merge`, `--info`, `--baksmali`, `--install`.
- Téléchargement optionnel des platform-tools / build-tools officiels Google depuis les Paramètres.
- Interface FR/EN, thème sombre/clair, glisser-déposer partout, journal coloré.

[1.0.2]: https://github.com/rerem8433/apktoolgui-linux/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/rerem8433/apktoolgui-linux/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/rerem8433/apktoolgui-linux/releases/tag/v1.0.0
