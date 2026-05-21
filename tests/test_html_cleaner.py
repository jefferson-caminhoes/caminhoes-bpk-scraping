from src.cleaner.html_cleaner import clean_html

DIRTY_HTML = """
<html>
<head><title>Consulta</title><script>alert('hack')</script><style>body{color:red}</style></head>
<body>
  <nav>Menu Home Projetos Logout</nav>
  <header>Sistema de Protocolos</header>
  <!-- comentário irrelevante -->
  <main>
    <h2>Consulta de Protocolo</h2>
    <p>Protocolo: 12345</p>
    <p>CNPJ: 12.345.678/0001-99</p>
    <table>
      <tr><th>Data</th><th>Status</th><th>Observação</th></tr>
      <tr><td>20/05/2026</td><td>Em análise</td><td>Aguardando documentação</td></tr>
    </table>
  </main>
  <footer>Rodapé: termos de uso, cookies, privacidade</footer>
</body>
</html>
"""


def test_removes_script_tags():
    result = clean_html(DIRTY_HTML)
    assert "alert" not in result
    assert "hack" not in result


def test_removes_style_tags():
    result = clean_html(DIRTY_HTML)
    assert "color:red" not in result


def test_removes_nav_and_footer():
    result = clean_html(DIRTY_HTML)
    assert "termos de uso" not in result
    assert "Menu Home" not in result


def test_preserves_protocol_number():
    result = clean_html(DIRTY_HTML)
    assert "12345" in result


def test_preserves_status():
    result = clean_html(DIRTY_HTML)
    assert "Em análise" in result


def test_preserves_table_content():
    result = clean_html(DIRTY_HTML)
    assert "20/05/2026" in result
    assert "Aguardando documentação" in result


def test_removes_html_comments():
    result = clean_html(DIRTY_HTML)
    assert "comentário irrelevante" not in result


def test_returns_string():
    result = clean_html("<html><body><p>Protocolo 99</p></body></html>")
    assert isinstance(result, str)
    assert len(result) > 0


def test_empty_html_returns_empty_string():
    result = clean_html("")
    assert result == ""
