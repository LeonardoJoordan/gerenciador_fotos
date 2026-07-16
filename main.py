import sys
import os
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    # Cria a instância principal do aplicativo Qt
    app = QApplication(sys.argv)
    
    # Define o nome da aplicação para o sistema operacional
    app.setApplicationName("Gerenciador de Fotos de Pessoal")
    app.setOrganizationName("ComSoc")

    # Instancia a janela principal que construímos em ui/main_window.py
    window = MainWindow()
    window.resize(1024, 720) # Um tamanho padrão confortável para iniciar
    window.show()

    # Executa o loop principal de eventos do Qt e fecha de forma limpa quando encerrado
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
