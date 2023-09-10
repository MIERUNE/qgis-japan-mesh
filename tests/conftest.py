import os
import sys
from pathlib import Path
from typing import Iterable

import pytest
from qgis.core import QgsApplication
from qgis.gui import QgsGui

from japanese_grids import classFactory


@pytest.fixture(autouse=True, scope="session")
def qgis_app(tmp_path_factory) -> Iterable[QgsApplication]:
    # profile directory
    profile_path = tmp_path_factory.mktemp("profile")
    os.environ["QGIS_CUSTOM_CONFIG_PATH"] = str(profile_path)

    app = QgsApplication([], GUIenabled=True)
    app.initQgis()
    QgsGui.editorWidgetRegistry().initEditors()

    # Initialize processing plugin
    path = str((Path(app.pkgDataPath()) / "python" / "plugins").resolve())
    sys.path.append(str(path))
    from importlib import import_module

    Processing = import_module("processing.core.Processing")  # noqa: N806
    Processing.Processing.initialize()

    yield app

    app.exitQgis()


@pytest.fixture()
def provider(qgis_app: QgsApplication) -> Iterable[None]:
    plugin = classFactory(None)  # pyright: ignore
    plugin.initGui()

    yield None

    plugin.unload()
