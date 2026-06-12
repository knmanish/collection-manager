"""PyInstaller entry script.

Kept outside the package so it runs as a normal script while still importing the
installed ``collect`` package (whose modules use relative imports).
"""

from collect.desktop import main

if __name__ == "__main__":
    main()
