python setup.py install
build/scripts-2.7/md2latex report.md report.tex
pdflatex report.tex
rm report.aux
rm report.log
