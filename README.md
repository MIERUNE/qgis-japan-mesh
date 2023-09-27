# qgis-japan-mesh

[![Test](https://github.com/MIERUNE/qgis-japan-mesh/actions/workflows/test.yml/badge.svg)](https://github.com/MIERUNE/qgis-japan-mesh/actions/workflows/test.yml)

A QGIS Plugin to handle common Japanese grid square codes — 日本で使われている「標準地域メッシュ」と「国土基本図図郭」を QGIS で扱うためのプラグインです。機能は以下の通り：

- 「標準地域メッシュ」と「国土基本図図郭」の生成
- 「地域メッシュ統計」(e-Stat) の読み込み

機能の要望を歓迎いたします。 GitHub の Issue にどうぞ。

## Install (インストール)

本プラグインは QGIS Python Plugin Repository で公開されており、QGIS の「プラグインの管理とインストール」から &#8220;[Japanese Grid Mesh](https://plugins.qgis.org/plugins/japanese_grids/)&#8221; で検索してインストールできます。

主にプロセッシングプラグインとして機能します。プロセッシングツールボックスから呼び出して利用できます。

## License (ライセンス)

License: GPL v2

## Development (開発)

QGIS にデプロイする:

```console
make deploy
```
