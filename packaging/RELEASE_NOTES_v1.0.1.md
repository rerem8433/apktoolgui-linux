## APK Tool GUI Linux 1.0.1

Portage Linux natif (Python 3 + PyQt6) d'[APKToolGUI](https://github.com/AndnixSH/APKToolGUI) 3.4.0.0, par ParadoxXx Squad.

### Corrigé
- Icône absente dans **Infos APK** pour les applis récentes (AnyDesk, etc.) utilisant une icône adaptative XML avec des ressources obfusquées.

### Ajouté
- Nouveau moteur d'icône : PNG/WebP d'origine retrouvé par ID de ressource, sinon rendu de l'icône adaptative (fond, vecteur, inset, layer-list, dégradés).

### Installation (Linux Mint 21/22, Ubuntu 22.04+)
```
sudo apt install ./apktoolgui-linux_1.0.1_amd64.deb
```

Changelog complet : [CHANGELOG.md](https://github.com/rerem8433/apktoolgui-linux/blob/main/CHANGELOG.md)
