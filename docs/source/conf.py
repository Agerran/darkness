# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Darkness'
copyright = '2025, Gleb Vinogradov'
author = 'Gleb Vinogradov'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
]

templates_path = ['_templates']
exclude_patterns = []

autosummary_generate = True


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_static_path = ['_static']

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'furo'

extensions.append('autoapi.extension')

autoapi_dirs = ['../../src']
autoapi_options = [ 'members', 'undoc-members', 'show-inheritance', 'show-module-summary', 'imported-members', ]
autoapi_own_page_level = 'class'
suppress_warnings = ["autoapi"]

