"""Teste de fumaça da interface: carrega dados, executa as trilhas e gera o PDF sem erro."""
from streamlit.testing.v1 import AppTest

from conftest import RAIZ
from utils.entrada import adaptar_planilha, ler_arquivo


def _app_com_dados(arquivo):
    arq = RAIZ / "data" / arquivo
    dados, _ = adaptar_planilha(ler_arquivo(arq.name, arq.read_bytes()))
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=120)
    at.session_state["dados"] = dados
    at.run()
    return at


def test_fluxo_completo_sem_excecao():
    at = _app_com_dados("exemplo_dados.csv")
    assert not at.exception
    assert [t.label for t in at.tabs][:4] == ["Pesos UPS", "Trilha 1 — Valor Crítico",
                                             "Trilha 2 — Densidade de Kernel (KDE)", "Trilha 3 — Empírico de Bayes"]
    # as trilhas rodam sozinhas; o painel é a primeira aba dos resultados
    assert [t.label for t in at.tabs][-4:] == ["Painel", "Trilha 1 — Valor Crítico",
                                              "Trilha 2 — Densidade de Kernel (KDE)", "Trilha 3 — Empírico de Bayes"]
    # o relatório é gerado no clique: aqui, direto do que a sessão guardou
    from utils.relatorio import gerar_pdf_completo

    assert gerar_pdf_completo(at.session_state["df_proc"], at.session_state["resultados"])[:4] == b"%PDF"
    # mudar um peso refaz as análises com o peso novo
    antes = at.session_state["assinatura"]
    at.slider[2].set_value(30).run()
    assert not at.exception
    assert at.session_state["assinatura"] != antes
    assert at.session_state["df_proc"].attrs["pesos_ups"]["com_obito"] == 30


def test_trilha_sem_requisito_mostra_aviso_e_nao_quebra():
    at = _app_com_dados("exemplo_manual_trilha1.csv")          # sem coordenadas
    assert not at.exception
    assert any("latitude e longitude" in w.value for w in at.warning)


def test_planilha_de_sinistros_na_opcao_1_indica_a_segmentacao():
    """Um sinistro por linha, sem extensão nem VMD (como a base de SP no modelo do app): só a Trilha 2 roda, e as
    mensagens das Trilhas 1 e 3 indicam a Opção 2."""
    import pandas as pd

    bruto = pd.DataFrame({"segmento_id": [101, 102, 103, 104], "sem_vitima": [0, 0, 1, 0], "com_vitima": [1, 0, 0, 2],
                          "com_obito": [0, 1, 0, 0], "latitude": [-23.55, -23.56, -23.57, -23.58],
                          "longitude": [-46.63, -46.64, -46.65, -46.66], "volume_trafego": None,
                          "extensao_trecho": None, "ano": 2024})
    dados, _ = adaptar_planilha(bruto)
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=120)
    at.session_state["dados"] = dados
    at.run()
    assert not at.exception
    avisos = [w.value for w in at.warning]
    assert sum("Usar meus dados de sinistros" in a and "sinistro por linha" in a for a in avisos) == 2   # T1 e T3
    assert "kde" in at.session_state["resultados"]


def test_segmentacao_automatica_com_os_dados_embutidos():
    """Basta escolher a UF: o app segmenta com o SNV, os sinistros da PRF e o VMD embutidos e roda as trilhas."""
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300)
    at.run()
    assert not at.exception
    # barra lateral: “Entrada de dados”, com os sinistros próprios, as outras formas e o bloco avançado, nessa ordem
    assert [h.value for h in at.sidebar.header] == ["Entrada de dados"]
    assert [e.label for e in at.sidebar.expander] == ["Usar meus dados de sinistros", "Outras formas de entrada",
                                                      "Atualizar a malha ou o VMD (avançado)"]
    at.multiselect(key="ufs_0").set_value(["DF"]).run()
    assert not at.exception
    dados = at.session_state["dados"]
    assert dados["codigo_snv"].str.contains("DF").all() and dados["volume_trafego"].notna().all()
    assert set(at.session_state["resultados"]) == {"vc", "kde", "bayes"}
    assert any("de cerca de 1 km em DF" in s.value for s in at.success)


def _clicar(at, texto):
    botao = next(b for b in at.button if texto in b.label)
    botao.click().run()
    assert not at.exception, at.exception


def test_primeiros_passos_abre_os_exemplos():
    """O botão de Primeiros passos abre o guia; os botões do guia carregam o exemplo urbano
    (recorte do Infosiga embutido) e o de rodovia (PRF no DF), e o guia fecha."""
    from utils import dados_publicos as dp

    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300)
    at.run()
    _clicar(at, "Primeiros passos")
    assert at.session_state["guia"] and any("Primeiros passos" in h.value for h in at.header)
    if dp.exemplo_urbano():
        _clicar(at, "Abrir o exemplo urbano")
        assert not at.session_state["guia"] and at.session_state["exemplo"] == "urbano"
        assert "exemplo urbano" in at.session_state["descricao_fonte"]
        dados = at.session_state["dados"]
        assert (dados["fonte"] == "OpenStreetMap").any()
        assert {"vc", "kde"} <= set(at.session_state["resultados"])
    _clicar(at, "Primeiros passos")
    _clicar(at, "Abrir o exemplo de rodovia")
    assert at.session_state["exemplo"] is None and "sinistros da PRF" in at.session_state["descricao_fonte"]
    assert at.session_state["dados"]["codigo_snv"].str.contains("DF").all()


def test_manual_de_utilizacao_na_barra_lateral_e_no_guia():
    """O Manual de Utilização fica a um clique, na barra lateral e no fim dos Primeiros passos; o PDF é servido pelo
    próprio app (pasta static/)."""
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300)
    at.run()
    assert not at.exception
    links = [b for b in at.sidebar.link_button if "Manual de Utilização" in b.proto.label]
    assert len(links) == 1
    url = links[0].proto.url
    assert url.startswith("./app/static/")
    assert (RAIZ / "static" / url.removeprefix("./app/static/")).read_bytes()[:4] == b"%PDF"
    _clicar(at, "Primeiros passos")
    assert sum("Manual de Utilização" in b.proto.label for b in at.link_button) == 2


def test_trilha1_lista_a_frequencia_primeiro_com_a_severidade_como_padrao():
    """Métodos na ordem do Manual (frequência, depois severidade); a severidade é o padrão, como no fluxograma do
    Manual quando há a gravidade dos sinistros."""
    at = _app_com_dados("exemplo_dados.csv")
    metodo = next(s for s in at.selectbox if s.label == "Método" and "severidade" in str(s.value))
    assert metodo.options[0].startswith("Valor crítico de frequência")
    assert at.session_state["resultados"]["vc"]["Indice"].notna().all()
