import os
import sys

sys.path.insert(0, os.path.abspath("../../nethermind/entro"))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "entro"
copyright = "2023, Nethermind"
author = "Nethermind"
release = "0.0.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
]

autosummary_generate = True
autodoc_member_order = "groupwise"
autoclass_content = "class"
autodoc_class_signature = "separated"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "web3": ("https://web3py.readthedocs.io/en/stable/", None),
    "eth_typing": ("https://eth-typing.readthedocs.io/en/stable/", None),
}

templates_path = ["_templates"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_book_theme"
html_title = "Nethermind Entro Documentation"
html_theme_options = {
    "show_toc_level": 2,
    "logo": {
        "repository_url": "https://github.com/nethermindEth/entro",
        "use_repository_button": True,
        "image_light": "_static/logo-light.svg",
        "image_dark": "_static/logo-dark.svg",
        "link": "https://nethermind.io",
    },
}

html_static_path = ["_static"]
