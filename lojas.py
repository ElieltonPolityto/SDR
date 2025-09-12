def lojas_selecionadas(loja:str): # Função para seleção dos arquivos das lojas
# POTENCIAS: Potencias em kW das resistências de degelo   
# ARQUIVOS: Caminhos e nomes dos arquivos com os dados
    match loja:
        case "Atacadão Bangu RJ":
            ARQUIVOS = {
                "Cam Congelados Eco2Pack L1": r"data/atacadao_bangu_RJ/L1.csv",
                "Cam Congelados Eco2Pack L2": r"data/atacadao_bangu_RJ/L2.csv",
                    }
            POTENCIAS = {
            "Cam Cong L1": 10.0,
            "Cam Cong L2": 10.0,
                    }
        case "Atacadão Palmas TO":
            ARQUIVOS = {
                "Cam Cong L1": r"data/atacadao_palmas_TO/L1.csv",
                "Cam Cong L2": r"data/atacadao_palmas_TO/L2.csv",
                "Cam Cong L3": r"data/atacadao_palmas_TO/L3.csv",
                    }
            POTENCIAS = {
                "Cam Cong L1": 10.0,
                "Cam Cong L2": 10.0,
                "Cam Cong L3": 10.0,
                    }   
        case _:
            ARQUIVOS = {None:None}
            POTENCIAS = {None:None}
    return ARQUIVOS, POTENCIAS