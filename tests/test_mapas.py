import folium
import pandas as pd
from folium.plugins import HeatMap

from utils.mapas import mapa_kde


def test_mapa_da_trilha_2_abre_so_com_o_mapa_de_calor():
    df = pd.DataFrame({"segmento_id": list("abcd"), "latitude": [-15.80, -15.81, -15.82, -15.83],
                       "longitude": [-47.90, -47.91, -47.92, -47.93], "densidade": [1, 2, 3, 4],
                       "nivel_densidade": [1, 2, 3, 4], "indice_densidade": [10, 40, 70, 100],
                       "UPS": [1, 4, 28, 5], "Critico": [False, False, False, True]})
    m = mapa_kde(df)
    camadas = list(m._children.values())
    calor = [c for c in camadas if isinstance(c, HeatMap)]
    quartis = [c for c in camadas if isinstance(c, folium.GeoJson)]
    assert len(calor) == 1 and calor[0].show
    assert len(quartis) == 4 and not any(c.show for c in quartis)
    # o calor não pode quebrar o mapa montado numa aba oculta (tamanho zero)
    html = m.get_root().render()
    assert html.find("_redrawOriginal") < html.find("L.heatLayer(")
