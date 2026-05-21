import pytest

PROTOCOL_NOT_FOUND_HTML = """
<html><head><title>Consulta</title></head>
<body>
  <main>
    <p>Protocolo não encontrado no sistema.</p>
    <p>Por favor, verifique o número informado.</p>
  </main>
</body>
</html>
"""

STATUS_EM_ANALISE_HTML = """
<html><head></head>
<body>
  <main>
    <h2>Resultado da Consulta</h2>
    <p>Protocolo: 12345</p>
    <p>CNPJ: 12.345.678/0001-99</p>
    <p>Status: Em análise</p>
    <table>
      <tr><th>Data</th><th>Andamento</th></tr>
      <tr><td>20/05/2026</td><td>Aguardando documentação complementar</td></tr>
    </table>
  </main>
</body>
</html>
"""

EMPTY_HTML = ""

NOISY_HTML = """
<html>
<head><script>var x=1;</script><style>.a{color:red}</style></head>
<body>
  <nav>Home Projetos Sair</nav>
  <div class="cookie-banner">Usamos cookies. Aceitar</div>
  <main>
    <p>Protocolo: 99999</p>
    <p>Situação: Aprovado</p>
    <p>Última movimentação: 10/01/2026</p>
  </main>
  <footer>© 2026 Prefeitura. Termos de uso.</footer>
</body>
</html>
"""
