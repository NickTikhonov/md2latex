import re
import mistune

__version__ = '0.0.2'
__author__ = 'Kavin Yao <kavinyao@gmail.com>'
__all__ = ['MarkdownToLatexConverter']

def newline(func):
    """Insert double newline at the beginning of string."""
    def inner(*args, **argv):
        return '\n\n%s' % func(*args, **argv)

    return inner


class MetaRenderer(mistune.Renderer):
    """Renderer used rendering meta section.

    The meta section is separated from main body by an hrule (---) and
    contains two parts:
    1. a first-level heading
    2. a list of metadata in the format: - <meta_key>: <meta_value>

    As a result, overriding the header and list* rendering methods is
    sufficient. autolink is also overriden to support email in author."""

    def header(self, text, level, raw=None):
        return '\\title{%s}' % text

    @newline
    def list(self, body, ordered=True):
        return '\\author{%s}' % body

    def list_item(self, text):
        _, meta_key, meta_val = re.split(r'^([^:]+):\s+', text, maxsplit=1)
        if meta_key != 'author':
            return ''

        authors = re.split(', +', meta_val.rstrip())
        return '\n\\and\n'.join(authors)

    def autolink(self, link, is_email=False):
        return r'\\\texttt{%s}' % link


class LatexRenderer(mistune.Renderer):
    """Renderer for rendering markdown as LaTeX.

    Only a subset of mistune-flavored markdown is supported, which will be
    translated into a subset of LaTeX."""

    FOOTNOTE = 'FTNT-MAGIC'

    use_block_quote = False
    used_packages = []

    def __init__(self):
        super(mistune.Renderer, self).__init__()
        self.footnotes_ = {}

    def not_support(self, feature):
        raise NotImplemented('%s is not supported yet.' % feature)

    @newline
    def block_code(self, code, lang=None):
        self.used_packages.append('listings')
        code = code.rstrip()
        lang_syntax = ''
        if lang is not None:
            lang_syntax = '[language=%s]' % lang.title()
        return '\\begin{lstlisting}%s\n%s\n\\end{lstlisting}' % (lang_syntax, code)

    @newline
    def block_quote(self, text):
        """Ref: http://tex.stackexchange.com/a/4970/43978"""
        self.use_block_quote = True
        return '\\begin{blockquote}%s\n\\end{blockquote}' % text

    def block_html(self, html):
        self.not_support('Block HTML')

    @newline
    def header(self, text, level, raw=None):
        if level > 3:
            self.not_support('Header > 3')

        section = ('sub'*(level-1)) + 'section'
        return '\\%s{%s}' % (section, text)

    @newline
    def hrule(self):
        """Ref: http://tex.stackexchange.com/a/17126/43978"""
        return r'\noindent\rule{\textwidth}{0.4pt}'

    @newline
    def list(self, body, ordered=True):
        if ordered:
            self.used_packages.append('enumerate')
            return '\\begin{enumerate}\n%s\\end{enumerate}' % body
        else:
            return '\\begin{itemize}\n%s\\end{itemize}' % body

    def list_item(self, text):
        return '    \\item %s\n' % text

    @newline
    def paragraph(self, text):
        return '%s' % text

    def render_row(self, row, formatting="%s"):
        return " & ".join(map(lambda x: formatting % x.split('|')[0], row)) \
            + "\\\\\n"

    def render_align_options(self, row):
        return " ".join(map(lambda x: x.split('|')[1][0], row))

    @newline
    def table(self, header, body):
        head_cells = header[:-3].split('||')
        align_options = self.render_align_options(head_cells)
        table_contents = self.render_row(head_cells, formatting="\\textbf{%s}") \
            + "\\hline\n"

        body_rows = body[:-3].split('|||')
        for row in body_rows:
            table_contents += self.render_row(row.split('||'))

        return '''
\\begin{table}[h]
\\centering
\\begin{tabular}{%s}
\\hline
%s\\hline
\\end{tabular}
\\end{table}''' % (align_options, table_contents)

    def table_row(self, content):
        return "{}|||".format(content[:-2])

    def table_cell(self, content, header=False, align=False):
        return "{}|{}||".format(content, align)

    def double_emphasis(self, text):
        """Ref: http://tex.stackexchange.com/q/14667/43978"""
        return '\\textbf{%s}' % text

    def emphasis(self, text):
        return '\\emph{%s}' % text

    def codespan(self, text):
        return '\\texttt{%s}' % text

    def linebreak(self):
        return r'\\'

    def strikethrough(self, text):
        self.used_packages.append('ulem')
        return '\\sout{%s}' % text

    def autolink(self, link, is_email=False):
        self.used_packages.append('hyperref')

        if is_email:
            return r'\href{mailto:%s}{%s}' % (link, link)
        else:
            return r'\url{%s}' % link

    def link(self, link, title, text):
        if 'javascript:' in link:
            # for safety
            return ''

        self.used_packages.append('hyperref')

        # title is ignored
        return r'\href{%s}{%s}' % (link, text)

    def image(self, src, title, text):
        self.used_packages.append('graphicx')
        return '''
\\begin{figure}[ht]
\\centering
    \\includegraphics[width=1.0\\textwidth]{%s}
    \\caption{%s}
    \\label{%s}
\\end{figure}''' % (src, text, title)

    def raw_html(self, html):
        self.not_support('Inline HTML')

    def footnote_ref(self, key, index):
        # content will be patched later
        return '\\footnote{%s-%s}' % (self.FOOTNOTE, key)

    def footnote_item(self, key, text):
        # store footnotes for patch
        self.footnotes_[key] = text.strip()
        # return empty string as output
        return ''

    def footnotes(self, text):
        # return empty string as output
        return ''


class MarkdownToLatexConverter(LatexRenderer):
    meta_renderer = MetaRenderer()

    def convert(self, doc):
        try:
            meta, body = doc.split('---', 1)
        except ValueError:
            raise ValueError('Your document seems missing the meta part.')

        title = self.parse_meta(meta)
        body = self.parse_body(body)

        template = '''\\documentclass{article}

%s

%s
\\begin{document}

%s

\\maketitle
%s

\\end{document}'''

        return template % (self.resolve_packages(),
                           self.resolve_commands(),
                           title,
                           body)

    def parse_meta(self, meta):
        md = mistune.Markdown(renderer=self.meta_renderer)
        return md.render(meta)

    def parse_body(self, content):
        md = mistune.Markdown(renderer=self)
        return self.resolve_footnotes(md.render(content))

    ### The following commands use properties set in LatexRenderer

    def resolve_footnotes(self, text):
        parts = re.split(r'%s-([^}]+)' % self.FOOTNOTE, text)
        new_parts = []
        for i, part in enumerate(parts):
            if i%2 == 0:
                # normal part
                new_parts.append(part)
            else:
                # footnote part
                new_parts.append(self.footnotes_[part])

        return ''.join(new_parts)

    def resolve_packages(self):
        packages = ['\\usepackage[bottom=1in,top=1in]{geometry}', '\\usepackage{parskip}']
        packageSyntax = {
            'enumerate': '\\usepackage{enumerate}',
            'hyperref': '\\usepackage[pdftex,colorlinks,urlcolor=blue]{hyperref}',
            'graphicx': '\\usepackage{graphicx}',
            'listings': '\\usepackage{listings}',
            'ulem': '\\usepackage{ulem}',
        }      

        for package_name in set(self.used_packages):
            packages.append(packageSyntax[package_name])

        packages.append('\n\\geometry{letterpaper}')

        return '\n'.join(packages)

    def resolve_commands(self):
        if self.use_block_quote:
            return r"""
\newenvironment{blockquote}{%
  \par%
  \medskip
  \leftskip=4em\rightskip=2em%
  \noindent\ignorespaces}{%
  \par\medskip}
"""
        else:
            return ''
