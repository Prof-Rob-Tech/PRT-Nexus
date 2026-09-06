import os
import time
from PySide6.QtCore import QThread, Signal
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class Chip7Worker(QThread):
    # Sinais exigidos pela interface da View
    progresso = Signal(str, int)          # (mensagem, porcentagem_global)
    item_progresso = Signal(str, int)     # (num_str, porcentagem_item)
    item_concluido = Signal(dict)         # dict(num, titulo, caminho, status)
    concluido = Signal(bool, str)         # (sucesso, mensagem_final)

    def __init__(self, url, email, senha, destino, modo_avulso=False, parent=None):
        super().__init__(parent)
        self.url = url
        self.email = email
        self.senha = senha
        self.destino = destino
        self.modo_avulso = modo_avulso

    def run(self):
        driver = None
        try:
            self.progresso.emit("A iniciar o Google Chrome...", 10)
            
            # Inicializa o Chrome de verdade
            options = webdriver.ChromeOptions()
            # options.add_argument('--headless') # Tira o cardinal se quiseres que o Chrome rode invisível no fundo
            driver = webdriver.Chrome(options=options)
            
            self.progresso.emit("A aceder ao Chip 7...", 25)
            # Vai para o link que colaste na tela
            driver.get(self.url)
            time.sleep(3) # Espera a página carregar
            
            # ---------------------------------------------------------
            # PARTE DO LOGIN
            # ---------------------------------------------------------
            self.progresso.emit("A preencher dados de login...", 40)
            
            # NOTA: Estes seletores (input[type='email']) são genéricos. 
            # Pode ser necessário ajustar de acordo com o código HTML real do site Chip 7.
            try:
                email_input = driver.find_element(By.CSS_SELECTOR, "input[type='email'], input[name='email']")
                email_input.send_keys(self.email)
                
                senha_input = driver.find_element(By.CSS_SELECTOR, "input[type='password'], input[name='password']")
                senha_input.send_keys(self.senha)
                
                time.sleep(1)
                
                btn_login = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                btn_login.click()
                time.sleep(5) # Espera entrar na plataforma
            except Exception as e:
                print(f"Aviso: Não encontrou os campos de login na primeira página. Erro: {e}")

            # ---------------------------------------------------------
            # PARTE DE CAPTURA E DOWNLOAD (EXEMPLO)
            # ---------------------------------------------------------
            self.progresso.emit("A mapear vídeos...", 60)
            time.sleep(3)
            
            # Simulando a extração de um vídeo que encontrou na página
            titulo_aula = "Aula Extraída - Chip 7"
            self.progresso.emit(f"A descarregar: {titulo_aula}...", 80)
            
            # Aqui entraria o comando de download real. 
            time.sleep(3) # Finge o tempo de download do vídeo
            
            # Manda para a interface (fica verde na tabela!)
            self.item_concluido.emit({
                "num": "1",
                "titulo": titulo_aula,
                "caminho": os.path.join(self.destino, "aula_01_chip7.mp4"),
                "status": "Concluído"
            })

            self.progresso.emit("Processo Finalizado!", 100)
            self.concluido.emit(True, "Processo do Chip 7 finalizado com sucesso!")

        except Exception as e:
            self.concluido.emit(False, f"Erro no motor do Chip 7: {str(e)}")
        finally:
            # Fecha o navegador quando acaba ou se der erro
            if driver:
                driver.quit()