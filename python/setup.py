from setuptools import setup, find_packages

setup(
    name="frfr-pdf",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pdfplumber>=0.10.0",
        "PyMuPDF>=1.23.0",
        "PyPDF2>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "frfr-pdf=frfr_pdf.extractor:main",
        ],
    },
    python_requires=">=3.9",
)
