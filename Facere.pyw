# -*- coding: utf-8 -*-

import yagmail
import ftplib
import sys
import urllib2
import os
import crcmod
import sqlite3  
import serial
import time
import re
import glob
import subprocess
import datetime
from IPy import IP
# librerie creazione data-matrix
from pylibdmtx.pylibdmtx import encode


#librerie stampa etichette
from PIL import Image
import zpl
import requests
import win32print

import sys
from PyQt4 import QtCore, QtGui, uic 
from PyQt4.QtGui import QFileDialog, QApplication, QMainWindow, QPushButton, QWidget, QMessageBox

import pyodbc # PER CONNETTERSI AD AZURE
qtCreatorFile = "circuito_collaudo_RLU_last.ui" # layout main window.

qtCreatorFile_new_old = "new_old.ui" #layout prima finestra per scegliere se collaudare un nuovo device o uno vecchio
qtCreatorFile_rlu_rluB = "rlu_rlub.ui" #layout seconda finestra per scegliere la tipologia di dispositivo
qtCreatorFile_rlu_rluB_again = "rlu_rlub_again.ui" #layout seconda finestra per scegliere la tipologia di dispositivo 

oracolo = False
oracoloBin = ''
path = ''
path_fw = ''


ser = serial.Serial()
ser.baudrate = 115200
ser.bytesize = serial.EIGHTBITS #number of bits per bytes
ser.parity = serial.PARITY_NONE #set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE #number of stop bits

ser.timeout = 0             #non-block read
ser.xonxoff = False     #disable software flow control
ser.rtscts = False     #disable hardware (RTS/CTS) flow control
ser.dsrdtr = False       #disable hardware (DSR/DTR) flow control
ser.writeTimeout = 2     #timeout for write

tentativi = 0 # usato per i retry istantanei nel caso in cui ci sia un nack, prima di assegnarlo, riprovo.

Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)
Ui_new_old, QtBaseClass = uic.loadUiType(qtCreatorFile_new_old)
Ui_rlu_rlub, QtBaseClass = uic.loadUiType(qtCreatorFile_rlu_rluB)
Ui_rlu_rlub_again, QtBaseClass = uic.loadUiType(qtCreatorFile_rlu_rluB_again)

# CSS per lo styling della barra - non lo uso ora perchè mi crea problemi alla dimensione della stessa 
RED_STYLE = """

QProgressBar::chunk {
    background-color: red;
	}
"""




class MyApp(QtGui.QMainWindow, Ui_MainWindow):

    """ Ritorna le porte COM disponibili nel PC ( sia Win che Linux ) dove è stato avviato il programma """
    def serial_ports(self):
     
      if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
      elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
      elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
      else:
        raise EnvironmentError('Unsupported platform')

      result = []
      for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
      return result
   
    
   #abilita disabilita i pulsanti della casella relativa all'eliminazione di un device collaudato
    def toggleGroupBox_success(self,state):
       if state > 0:
         self.label_4.setEnabled(True)
         self.Button_sn.setEnabled(True)
         self.lineEdit_sn.setEnabled(True)
         self.listWidget_3.setEnabled(True)
         
       else:
         
         self.label_4.setEnabled(False)
         self.Button_sn.setEnabled(False)
         self.lineEdit_sn.setEnabled(False)
         self.listWidget_3.setEnabled(False)
	
    #elimina dal DB il device già collaudato e corrispondente al seriale inserito	
    def deleteWrongRLU(self) :
        
        sn=self.lineEdit_sn.text()
        self.deleteFromRlu_sngpt(sn)
        self.label_delete.setStyleSheet("color:green")
        self.label_delete.setText("operazione completata")
        self.lineEdit_sn.setText("")
		
		
    """Costruttore, qui referenzio i widget e gestisco il flusso di lavoro mediante gli eventi
	     @Param : tipo di device : RLU/RLU_B - quantità : 0-n - eventuale ID del device da ricollaudare - nack collaudo precedente. Se non presenti vengono passati valori nulli  """
    def __init__(self, rlu_type, numDevice, id_retry, nack, hw_version,pc_version,printer_s,printer_f,online_printer_success,online_printer_fail,serialNumberGPT):
        
        
        
		
        self.create_db()
		
        #array dove salvo la lista di porte COM disponibili 
        porte=[]
        porte= self.serial_ports()
       	
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
		
		  # gestisce la UI ed evita che si verifichino dei freeze
        gui=QtGui.QApplication.processEvents
        #imposto una dimensione fissa della finestra 
        self.setFixedSize(1300, 1000)
		
        #aggiungo al dropdown le porte COM disponibili
        self.COM_edit.addItems(porte)
		
        
    
        
		  #mostro a video la matricola,l'id che si sta per collaudare, l'ultimo esito, la data  ed il numero di collaudi sia che sia nuovo che retry
		  #######################################################################################
        if id_retry!=None :
		   self.matCol_label.setText(id_retry+" / "+serialNumberGPT)
		   self.ultimoEsito_label_2.setStyleSheet("color:red")
		   self.ultimoEsito_label_2.setText(nack)
		   self.lcdNumber.setStyleSheet("color:red")
		   self.lcdNumber.display(1)
		   timestamp_collaudo = int(MainWindow.select_generica(self,"SELECT timestamp FROM RLU WHERE cod_prod =? ",id_retry))
		   data_collaudo= datetime.datetime.fromtimestamp(timestamp_collaudo)
		   self.data_label_2.setStyleSheet("color:red")
		   self.data_label_2.setText(str(data_collaudo))
        else: 
         self.matCol_label.setText(self.serialMaker()+" / "+serialNumberGPT)
         self.ultimoEsito_label_2.setStyleSheet("color:green")
         self.ultimoEsito_label_2.setText("")
        ########################################################################################
		
		  
		
        #selezione file binario boot
        self.selectFile_toolButton.clicked.connect(self.select_file)
        #selezione file binario fw
        self.selectFile_toolButton_2.clicked.connect(self.select_file_fw)
		
        #pulsante ok boot
        path=self.buttonBox.accepted.connect(self.right_file)
        		
        #pulsante canc svuota path
        self.buttonBox.rejected.connect(self.wrong_file)
		
        #pulsante ok fw
        path_fw=self.buttonBox_2.accepted.connect(self.right_file_fw)      
        #pulsante canc svuota path
        self.buttonBox_2.rejected.connect(self.wrong_file_fw)
       
	     #al click sulla checkbox "problemi con la stampa?" abilita gli elementi della casella sottostante
        self.checkBox.stateChanged.connect(self.toggleGroupBox_success)
        #elimina dal DB la riga corrispondente al seriale inserito 
        self.Button_sn.clicked.connect(self.deleteWrongRLU)
		
		  #se è stato selezionato RLU il collaudo è completo, altrimenti con RLU_B non testo irda2 e misura corrente
        
        self.avviaCollaudotoolButton.clicked.connect(lambda:self.avviaCollaudo(numDevice, tentativi, rlu_type, id_retry,gui,hw_version,pc_version,printer_s,printer_f,online_printer_success,online_printer_fail,serialNumberGPT))
        #imposto la tipologia di device che si sta collaudando ovvero RLU/RLU_B
        self.groupBox.setTitle(rlu_type)       
        #da implementare e gestire lo stop del collaudo TODO ?
        #self.fermaCollaudotoolButton.clicked.connect(?)


        #PULSANTI DEBUG
        #TODO delete
        #self.btn_abilitaPrg.clicked.connect(lambda:self.abilita_programmazione(tentativi,"28B"))
        #self.btn_disabilitaPrg.clicked.connect(lambda:self.disabilita_programmazione(tentativi,"28B"))
        #self.btn_IRDA2.clicked.connect(lambda:self.test_irda2(tentativi))
        #self.btn_getKey.clicked.connect(lambda:self.get_key(tentativi))
        #self.btn_testTrans.clicked.connect(lambda:self.test_transceiver(tentativi))
        #self.btn_ricarica.clicked.connect(lambda:self.misura_corrente_ricarica(tentativi))
        self.btn_echo.clicked.connect(lambda:self.echo())
        #pulsante "ProgrammaFW"
        #self.btn_shellCmd.clicked.connect(self.programma_fw)
        #/PULSANTI DEBUG
		  # pulsante OK che prende l'ip 
        #self.Button_z.clicked.connect(lambda:self.getIPFromLabel())
		
    def dateFromTimestamp(self,codProd) :
        timestamp_collaudo = int(MainWindow.select_generica(self,"SELECT timestamp FROM RLU WHERE cod_prod =? ",codProd))
        data_collaudo= datetime.datetime.fromtimestamp(timestamp_collaudo)
        return data_collaudo

        
	""" Programma il fw nel device attualmente collegato al CDC """
    def programma_fw(self) :
        gui=QtGui.QApplication.processEvents
        gui()
       
        
        path = self.lineEdit.text()
        path_fw = self.lineEdit_2.text()
        #os.system('cd C:\\Program Files\\STMicroelectronics\\STM32 ST-LINK Utility\\ST-LINK Utility')
        #gui()
        os.system('ST-LINK_CLI.exe -c ID=0 SWD FREQ=0 UR')
        gui()
        os.system('ST-LINK_CLI.exe -ME')
        gui()
        time.sleep(2)
        os.system('ST-LINK_CLI.exe -P '+'"'+str(path)+'"'+' 0x08000000 –V after_programming')  #path bootloader 
        gui()
        time.sleep(2)
        os.system('ST-LINK_CLI.exe -P '+'"'+str(path_fw)+'"'+' 0x0800c800 –V after_programming') #path fw
        gui()
        time.sleep(6)
        os.system('ST-LINK_CLI.exe -Rst')
		
		
	"""Resetta le progress bar e le label ad ogni collaudo avvenuto""" 
    def resetBarreLabel(self) :
        self.progressBar.reset()
        self.progressBar_2.reset()
        self.progressBar_3.reset()
        self.progressBar_4.reset()
        self.progressBar_5.reset()
        self.progressBar_6.reset()
        self.progressBar_7.reset()
        
        self.labelBar_1.setText("")
        self.labelBar_2.setText("")
        self.labelBar_3.setText("")
        self.labelBar_4.setText("")
        self.labelBar_5.setText("")
        self.labelBar_6.setText("")
        self.labelBar_7.setText("")
        self.matCol_label.setText("")
        self.ultimoEsito_label_2.setText("")
        self.data_label_2.setText('')
        self.lcdNumber.display(0)

    def onOffButtons(self,enabled) :
        self.pushButton_home.setEnabled(enabled)
        self.avviaCollaudotoolButton.setEnabled(enabled)
        self.selectFile_toolButton.setEnabled(enabled)
        self.selectFile_toolButton_2.setEnabled(enabled)
        self.buttonBox.setEnabled(enabled)
        self.buttonBox_2.setEnabled(enabled)
        self.btn_echo.setEnabled(enabled)
        self.COM_edit.setEnabled(enabled)		
		
    """Istanzia un popup da mostrare a video, customizzabile con messaggi specifici
	     @Param : testo e titolo del messaggio da mostrare -  riepilogo ovvero query dal db dei nack/ack/ack_2/nack_2"""
    @staticmethod
    def createMessageBox(self,testo,titolo,riepilogo) :
	 
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setText(testo) 
        msgBox.setWindowTitle(titolo)
        msgBox.setDetailedText("Riepilogo collaudo :"+str(riepilogo))  
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        

        returnValue = msgBox.exec_()

    	
    def createMessage(self,testo,titolo,riepilogo,cancel) :
	 
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setText(testo) 
        msgBox.setWindowTitle(titolo)
        if cancel :		
         msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        else :
         msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding) 
        scelta = msgBox.exec_()
        return scelta
        
        
    def showDialog(self,prodCode):
        #query_seriale = 'SELECT sn_gpt FROM RLU WHERE sn_gpt =?'
        
        num=''
        scelta_=0
        scelta=0
        num, ok = QtGui.QInputDialog.getText(self, 'Facere','Inserire il seriale:')
        #serialeDB=MainWindow.select_generica(self,query_seriale,num)
        if ok and num !='' and num:
         
         self.matCol_label.setText(prodCode+" / "+num)
         self.update_sn_gpt(num,prodCode)
         return 0
        elif ok and num =='' and QtGui.QInputDialog :
         scelta_=self.createMessage("INSERIRE UN SERIALE VALIDO ed INEDITO","ATTENZIONE",None,False)
        #elif  num == serialeDB :
         #scelta_=self.createMessage("INSERIRE UN SERIALE VALIDO ed INEDITO","ATTENZIONE",None,False)
        if scelta_==1024 :
         self.showDialog(prodCode)
        else :
         scelta=self.createMessage("Exit?","Terminare il collaudo?",None,True)
         #print scelta
	   
        if scelta!=1024 :
         self.showDialog(prodCode)
        else :
         self.deleteFromRlu(prodCode) # o num?
         app = QtGui.QApplication(sys.argv)
         sys.exit(app.exec_())
		
    
       
		
	"""Crea un seriale per i nuovi device.Se DB vuoto inizia con 1A altrimenti legge dal DB il seriale dell'ultimo oggetto collaudato e lo incrementa """
    def serialMaker(self) :
        numero=0
        lettera='A'
        # prendo dal DB l'ultimo elemento inserito
        queryLatest = "SELECT cod_prod FROM RLU WHERE ROWID IN ( SELECT max( ROWID ) FROM RLU );" 
        latestCodProdFromDB = MainWindow.select_generica(self,queryLatest,"")
        if latestCodProdFromDB!="" or latestCodProdFromDB!=None :
         #prelevo  la parte decimale per poterla poi incrementare
         decimale = re.findall(r'\d+', latestCodProdFromDB)
		   #prelevo anche la parte letterale
         stringa = re.findall(r'\D', latestCodProdFromDB)
         
         #decimale è una lista, la scorro ed isolo soltanto i numeri senza virgole e cazzi vari
		   #faccio la stessa cosa con stringa dato che i cast prendono solo ciò che è di loro competenza
         for item in decimale :
          numero= int(item)
         for item in stringa :
          lettera = str(item)
		  
         lettera.strip() #per sicurezza levo eventuali spazi
         
		  #qui gestisco il fatto che i seriali devono seguire l'ordine 0-999 A-Z
         if numero==999 :
          numero=0		
          if lettera=='A' :
           lettera_='B'
          if lettera=='B' :
           lettera_='C'
          if lettera=='C' :
           lettera_='D'
          if lettera=='D' :
           lettera_='E'
          if lettera=='E' :
           lettera_='F'
          if lettera=='F' :
           lettera_='G'
          if lettera=='G' :
           lettera_='H'
          if lettera=='H' :
           lettera_='I'
          if lettera=='I' :
           lettera_='J'
          if lettera=='J' :
           lettera_='K'
          if lettera=='K' :
           lettera_='L'
          if lettera=='L' :
           lettera_='M'
          if lettera=='M' :
           lettera_='N'
          if lettera=='N' :
           lettera_='O'
          if lettera=='O' :
           lettera_='P'
          if lettera=='P' :
           lettera_='Q'
          if lettera=='Q' :
           lettera_='R'
          if lettera=='R' :
           lettera_='S'
          if lettera=='S' :
           lettera_='T'
          if lettera=='T' :
           lettera_='U'
          if lettera=='U' :
           lettera_='V'
          if lettera=='V' :
           lettera_='W'
          if lettera=='W' :
           lettera_='X'
          if lettera=='X' :
           lettera_='Y'
          if lettera=='Y' :
           lettera_='Z'	
          startLetter = lettera_		   
         else:
          startLetter = lettera
		  
        startNumber = numero 
        startNumber+=1
        prodCode=str(startNumber)+startLetter
        
        return prodCode		
	
    """ E' Collegata al pulsante -Avvia Collaudo- esegue alcuni controlli sui requisiti quali connessione con il device, caricamento file necessari come bootloader e firmware. Ad ogni collaudo ultimato richiede l'interazione dell'utente che deve cliccare su un popup con il resoconto per procedere al collaudo del device successivo. A seconda della tipologia di device viene lanciata la funzione idonea"""
    def avviaCollaudo(self, numDevice, tentativi, rlu_type, id_retry,gui,hw_version,pc_version,printer_s,printer_f,online_printer_success,online_printer_fail,serialNumberGPT) :
       
	   
       self.onOffButtons(False) #disabilito i pulsanti
	   
       self.labelBar_1.setText("attendere...")
       #Id del device
       prodCode=''
	    #testo la connessione al device mediante l'invio di un echo
       connessione = self.echo()
       # da stampare nell'etichetta TODO
       data = datetime.datetime.now()
       ora = str(data.hour)+str(data.minute)
       data_only = str(data.strftime('%d%m%y'))
        
       # ###########################################
       ts = int(time.time())
       #data_from_ts = datetime.datetime.fromtimestamp(ts)	   
       #print "data from ts : "+str(data_from_ts)
       # #################### controllo che siano stati caricati i due file ########################
       bootloader = self.rightFile_label.text()
       firmware = self.rightFile_label_2.text()
	   
       boot_caricato=False
       firmware_caricato=False
	   
       if bootloader == 'File caricato con successo' and firmware == 'File caricato con successo' :
        boot_caricato=True
        firmware_caricato=True
       else :
        self.rightFile_label.setStyleSheet('color:red')
        self.rightFile_label.setText("file mancante o errato")
		
        self.rightFile_label_2.setStyleSheet('color:red')
        self.rightFile_label_2.setText("file mancante o errato")
        # ##########################################################################################
		
       if connessione and boot_caricato and firmware_caricato : 
	     #ciclo per quanti sono i device da collaudare   
        for x in range(numDevice):
         gui() # evita il freeze 
         query='SELECT ack,nack FROM RLU WHERE cod_prod = ?'
         query_retry='SELECT ack_2,nack_2 FROM RLU WHERE cod_prod = ?'
         report =""
		  #se retry il prodcode sarà corrispondente all'id_retry, altrimenti ne genero uno nuovo
         if id_retry!=None :
		    prodCode =id_retry
         else: 
          prodCode = self.serialMaker()
          #insert nel DB del prodcode e del tipo di device. Successivamente avvengono solo update
          self.insert_into_db(prodCode,"","",rlu_type,"","",hw_version,"","",ts,pc_version,serialNumberGPT,"") # fornisco le info che ho al momento
		  
         #dalla seconda iterazione in poi compare il messaggio ad ogni collaudo ultimato
         if  x > 0 and id_retry==None :
          # richiamo la funzione statica presente nell'altra classe e salvo il risultato della query
          report = MainWindow.select_generica(self,query,prodCode)
          #self.createMessageBox("cambia il device poi premi ok","collaudo in pausa",report)
          #serialNumberGPT=self.showDialog()
          #self.update_sn_gpt(serialNumberGPT,prodCode)
		  
          self.resetBarreLabel()
          self.showDialog(prodCode)
         #mostro a video l'id del device in collaudo dato che cambia ogni volta
         #self.matCol_label.setText(prodCode+" / "+serialNumberGPT)		 
         if rlu_type == 'RLU' :
          self.avviaCollaudoRLU(tentativi, prodCode,rlu_type,id_retry,printer_s,printer_f,online_printer_success,online_printer_fail)
         else :
		    self.avviaCollaudoRLU_B(tentativi, prodCode,rlu_type,id_retry,printer_s,printer_f,online_printer_success,online_printer_fail)
        # se retry il resoconto riguarda ack_2 e nack_2, altrimenti ack e nack 
        if id_retry==None :
          report = MainWindow.select_generica(self,query,prodCode)
        else :
          report = MainWindow.select_generica(self,query_retry,prodCode)
		  #popup operazione completata
        self.createMessageBox(self,"operazione completata","collaudo terminato",report)
        self.pushButton_home.setEnabled(True) #riabilito il pulsante
        
        #richiama funzione reset barre e label
        self.resetBarreLabel()
       else :
        self.createMessageBox(self,"porta COM errata o device spento o malfunzionante","selezionare un'altra porta","porta COM errata o device spento o malfunzionante")
        self.onOffButtons(True) #riabilito i pulsanti
		
		
	""" Triggera in sequenza le funzioni preposte al test del device RLU controllando l'esito di ciascuna e procedendo soltanto nel caso in cui quest'ultimo sia positivo"""	
    def avviaCollaudoRLU(self, tentativi, prodCode,rlu_type,id_retry,printer_s,printer_f,online_printer_success,online_printer_fail):
        # se esito è positivo allora proseguo con il collaudo, altrimenti interrompo
        esito=""
        final_esito=False
		
        
		
        esito=self.abilita_programmazione(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
        time.sleep(2)
        if esito!="fail":
         esito=self.disabilita_programmazione(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
        time.sleep(5)
        if esito!="fail":
         esito=self.test_irda2(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail) 
        time.sleep(2)
        if esito!="fail":
         esito=self.get_key(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
        time.sleep(2)
        if esito!="fail":
         esito=self.test_transceiver(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
        time.sleep(2)
        if esito!="fail":
         esito=self.misura_corrente_ricarica(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
         final_esito=True #indica che il collaudo è stato ultimato con successo 
        time.sleep(2)
		
		  #qr_code data matrix
        query_qr = "SELECT id_radio,cod_prod,type,hw_version,fw_version,timestamp,sitoprodcol,nack FROM RLU WHERE cod_prod = ?"
        data_qr=self.select_per_qr(query_qr,prodCode)
        
        nack_numero = self.nack_number(prodCode)
		  #id_radio da stampare sull'etichetta
        query_id_radio = 'SELECT id_radio FROM RLU WHERE cod_prod=?'
        id_radio= MainWindow.select_generica(self,query_id_radio,prodCode)
        #per stampante online TODO istruzione condizionale
        query_ip_ok = "SELECT IP_OK FROM Zebra"
        ip_address = MainWindow.select_generica(self,query_ip_ok,"")
        query_key = 'SELECT key FROM RLU WHERE cod_prod=?'
        key= MainWindow.select_generica(self,query_key,prodCode)
		
        #nel caso di secondo collaudo con esito positivo aggiorno il campo ack_2 e stampo l'etichetta positiva
        if id_retry!=None and final_esito :
             self.update_table_ack_2("collaudo_ok",prodCode) # update campo ack_2 se device ricollaudato
             self.dataMatrixGenerator(data_qr+"2 "+str(nack_numero))  #2 sono i tentativi essendo retry sono 2
             try : 
              self.citymonitorDB(id_radio,key) 
             except Exception, e :
              self.createMessageBox(self,"errore inserimento dati nel DB","ERRORE","device già collaudato")
              self.deleteFromRlu(prodCode)
              sys.exit(0)
             self.createLabel(prodCode,id_radio,printer,ip_address,printer_s,online_printer_success)
             self.sendMail(prodCode,id_radio,"collaudo_ok")			 
             
			 
        elif id_retry==None and final_esito :			             
             self.update_table_ack("collaudo_ok",prodCode)
             self.dataMatrixGenerator(data_qr+"1") #1 sono i tentativi
             try : 
              self.citymonitorDB(id_radio,key) 
             except Exception, e :
              self.createMessageBox(self,"errore inserimento dati nel DB","ERRORE","device già collaudato")
              self.deleteFromRlu(prodCode)
              sys.exit(0)
             self.createLabel(prodCode,id_radio,printer,ip_address,printer_s,online_printer_success)
             self.sendMail(prodCode,id_radio,"collaudo_ok")			 
              
	
    """ Triggera in sequenza le funzioni preposte al test del device RLU_B controllando l'esito di ciascuna e procedendo soltanto nel caso in cui quest'ultimo sia positivo. Non presenta test_irda e misura_corrente_ricarica"""	
    def avviaCollaudoRLU_B(self, tentativi, prodCode,rlu_type,id_retry,printer_s,printer_f,online_printer_success,online_printer_fail):
        # se esito è positivo allora proseguo con il collaudo, altrimenti interrompo
        esito=""
        final_esito=False
        
		
        esito=self.abilita_programmazione(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
        time.sleep(2)
        if esito!="fail":
         esito=self.disabilita_programmazione(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
        time.sleep(4)
        if esito!="fail":
         esito=self.get_key(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
        time.sleep(2)
        if esito!="fail":
         esito=self.test_transceiver(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
        time.sleep(2)
        if esito!= "fail":
         final_esito=True #indica che il collaudo è stato ultimato con successo 
        time.sleep(1)
		
		  #qr_code data matrix
        query_qr = "SELECT id_radio,cod_prod,type,hw_version,fw_version,timestamp,sitoprodcol FROM RLU WHERE cod_prod = ?"
        
        nack_numero = self.nack_number(prodCode)
        data_qr=self.select_per_qr(query_qr,prodCode)
		  #id_radio da stampare sull'etichetta
        query_id_radio = 'SELECT id_radio FROM RLU WHERE cod_prod=?'
        id_radio= MainWindow.select_generica(self,query_id_radio,prodCode)
        #per stampante online TODO istruzione condizionale
        query_ip_ok = "SELECT IP_OK FROM Zebra"
        ip_address = MainWindow.select_generica(self,query_ip_ok,"")
        query_key = 'SELECT key FROM RLU WHERE cod_prod=?'
        key= MainWindow.select_generica(self,query_key,prodCode)
		
        #nel caso di secondo collaudo con esito positivo aggiorno il campo ack_2 e stampo l'etichetta positiva
        if id_retry!=None and final_esito :
             self.update_table_ack_2("collaudo_ok",prodCode) # update campo ack_2 se device ricollaudato
             self.dataMatrixGenerator(data_qr+"2 "+str(nack_numero)) #2 sono i tentativi essendo retry sono 2
             try : 
              self.citymonitorDB(id_radio,key) 
             except Exception, e :
              self.createMessageBox(self,"errore inserimento dati nel DB","ERRORE","device già collaudato")
              self.deleteFromRlu(prodCode)
              sys.exit(0)
             self.createLabel(prodCode,id_radio,printer_s,ip_address,online_printer_success)
             self.sendMail(prodCode,id_radio,"collaudo_ok")			 
             
			 
        elif id_retry==None and final_esito :			             
             self.update_table_ack("collaudo_ok",prodCode)
             self.dataMatrixGenerator(data_qr+"1") #1 sono i tentativi 
             try : 
              self.citymonitorDB(id_radio,key) 
             except Exception, e :
              self.createMessageBox(self,"errore inserimento dati nel DB","ERRORE","device già collaudato")
              self.deleteFromRlu(prodCode)
              sys.exit(0)
             self.createLabel(prodCode,id_radio,printer_s,ip_address,online_printer_success)
             self.sendMail(prodCode,id_radio,"collaudo_ok")
             		 
             
    # prendo il nack dal DB e lo associo ad un numero che poi ritorno     
    def nack_number(self,prodCode) :
      query_nack = "SELECT nack FROM RLU WHERE cod_prod = ?"
      nack= MainWindow.select_generica(self,query_nack,prodCode)
      nack_error_list = ["comando non valido","err misura corrente","test IRDA_1 ko","test IRDA_2 ko","test IRDA_1,IRDA_2 ko","test transceiver non riuscito","test EEPROM non riuscito","test KEY non riuscito","corrente out of range","rssi out of range","errore generico"]
      for i in xrange(len(nack_error_list)) :
       if nack == nack_error_list[i] :
        return i+1
   
    def sendMail(self,codProd,id_radio,success_or_fail) :
      yag = yagmail.SMTP('lv.menowattge@gmail.com', 'menowattge')
      yag.send('controlloproduzione@menowattge.it',success_or_fail, 'collaudo effettuato :'+codProd+"-"+id_radio)	
		

    #genero il ST con crc16 TODO delete ? 
    #def system_title_generator(self):
    #    serialNumber = str(self.serialNumber_text.text())
    #    serialNumberReverse = serialNumber[::-1]
    #    crc16 = crcmod.predefined.Crc('crc-16-dnp')
    #    crc16_R = crcmod.predefined.Crc('crc-16-dnp')
    #    crc16_R.update(serialNumberReverse)
    #    crc16.update(serialNumber)
    #    snCrc16 = crc16.hexdigest()
    #    snCrc16_R = crc16_R.hexdigest()
        #inverto i bytes perche emiliano ha usato un dnp leggermente diverso
    #    snCrc16TwoLastBytes  = snCrc16[-2:]
    #    snCrc16TwoFirstBytes = snCrc16[:2]

    #    snCrc16TwoLastBytes_R  = snCrc16_R[-2:]
    #    snCrc16TwoFirstBytes_R = snCrc16_R[:2]

    #    system_title = 'D735'+snCrc16TwoLastBytes+snCrc16TwoFirstBytes+snCrc16TwoLastBytes_R+snCrc16TwoFirstBytes_R+'0102'

    #    return system_title

    #DEBUG funzione che nasce per stampare l'ST ma la uso per debug vari
    #def print_st(self):
        #st = self.system_title_generator()
     #   print st
        #self.progressBar.setValue(14.28571428571429)

        #self.update_table()


    #selezione file binario ################################SELEZIONE BOOTLOADER######################################
    def select_file(self):
        self.rightFile_label.setText('')
        self.lineEdit.setText(QFileDialog.getOpenFileName())

    #click 'OK'
    def right_file(self):
        path = self.lineEdit.text()
        if path != ''  and path[-8:]== 'boot.bin':
            self.rightFile_label.setStyleSheet('color: green')
            self.rightFile_label.setText('File caricato con successo')
            #oracoloBin = True
        else :
            path=''
            self.rightFile_label.setStyleSheet('color: red')
            self.rightFile_label.setText('Formato del file non corretto')
            #oracoloBin = False
            #debug
        return path

    #click 'Cancel'
    def wrong_file(self):
        path = ''
        self.rightFile_label.setText(path)
        self.lineEdit.setText(path)
        #debug
        
		
    # #################################################SELEZIONE FIRMWARE############################################		
    def select_file_fw(self):
        self.rightFile_label_2.setText('')
        self.lineEdit_2.setText(QFileDialog.getOpenFileName())

    #click 'OK'
    def right_file_fw(self):
        path = self.lineEdit_2.text()
       
        if path != '' and path[-6:]== 'fw.bin':
            self.rightFile_label_2.setStyleSheet('color: green')
            self.rightFile_label_2.setText('File caricato con successo')
            #oracoloBin = True
        else :
            path=''
            self.rightFile_label_2.setStyleSheet('color: red')
            self.rightFile_label_2.setText('Formato del file non corretto')
            #oracoloBin = False
            #debug
        return path

    #click 'Cancel'
    def wrong_file_fw(self):
        path = ''
        self.rightFile_label_2.setText(path)
        self.lineEdit_2.setText(path)
        #debug
        	
		
   # ##################################################################################################################

   # ###############################################DATABASE###########################################################

    #func per creare il DB # TODO lanciare all'avvio 
    def create_db(self):
        conn = sqlite3.connect('Database\\rluDB.db')
        conn.execute('CREATE TABLE IF NOT EXISTS RLU (cod_prod TEXT PRIMARY KEY, ack TEXT, nack TEXT, type TEXT, ack_2 TEXT, nack_2 TEXT, hw_version TEXT, fw_version TEXT, id_radio TEXT, timestamp TEXT, sitoprodcol TEXT, sn_gpt TEXT, key TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS Zebra ( IP_OK TEXT, IP_KO TEXT )')
        conn.close()
		


    
    def update_table_nack_2(self,error,prodCode):
       
        code = str(prodCode)
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""UPDATE RLU SET  nack_2 = ? WHERE cod_prod = ? """,(error,code,))
			
    def update_table_nack(self,error,prodCode):
       
        code = str(prodCode)
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""UPDATE RLU SET  nack = ? WHERE cod_prod = ? """,(error,code,))
			
    def update_table_ack_2(self,ok,prodCode):
       
        code = str(prodCode)
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""UPDATE RLU SET  ack_2 = ? WHERE cod_prod = ? """,(ok,code,))
			
    def update_table_ack(self,ok,prodCode):
       
        code = str(prodCode)
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""UPDATE RLU SET  ack = ? WHERE cod_prod = ? """,(ok,code,))
			
    def update_table_fw(self,fw_version,prodCode):
       
        code = str(prodCode)
        fw_version_ = str(fw_version)
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""UPDATE RLU SET  fw_version = ? WHERE cod_prod = ? """,(fw_version_,code,))
			
    def update_table_id_radio(self,id_radio,prodCode):
       
        code = str(prodCode)
        id_radio = str(id_radio)
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""UPDATE RLU SET  id_radio = ? WHERE cod_prod = ? """,(id_radio,code,))
			
    def update_table_key(self,key,prodCode):
       
        code = str(prodCode)
        key = str(key)
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""UPDATE RLU SET  key = ? WHERE cod_prod = ? """,(key,code,))
			
    def update_sn_gpt(self,serialNumberGPT,prodCode):
       
        code = str(prodCode)
        serialNumberGPT = str(serialNumberGPT)
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""UPDATE RLU SET  sn_gpt = ? WHERE cod_prod = ? """,(serialNumberGPT,code,))
	
    @staticmethod	
    def update_table_ip_ok(self,ip_ok):
       
        ip_okk = str(ip_ok)
        
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""DELETE FROM Zebra""")
            time.sleep(1)
            cursor.execute("""INSERT INTO Zebra(IP_OK,IP_KO) VALUES('','')""")
            time.sleep(1)
            cursor.execute("""UPDATE Zebra SET  IP_OK = ?""",(ip_okk,))
			
    @staticmethod
    def update_table_ip_ko(self,ip_ko):
       
        ip_koo = str(ip_ko)
        
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""UPDATE Zebra SET  IP_KO = ?""",(ip_koo,))

    def deleteFromRlu_sngpt(self,sn) :
       sn_ = str(sn)
        
       conn = sqlite3.connect('Database\\rluDB.db')
		
       with conn :
            cursor = conn.cursor()
            
            cursor.execute("""DELETE FROM RLU WHERE sn_gpt = ?""",(sn_,))




    def insert_into_db(self,prodCode,ACK,NACK,rlu_type,ack_2,nack_2,hw_version,fw_version,id_radio,ts,pc_version,serialNumberGPT,key):
       
        list = [str(prodCode),str(ACK),str(NACK),str(rlu_type),str(ack_2),str(nack_2),str(hw_version),str(fw_version),str(id_radio),str(ts),str(pc_version),str(serialNumberGPT),str(key)]
        conn = sqlite3.connect('Database\\rluDB.db')
        with conn :
         cursor = conn.cursor()
         cursor.executemany('INSERT INTO RLU values (?,?,?,?,?,?,?,?,?,?,?,?,?)',[list])
		 
    def select_per_qr(self,query,where_var):
        conn = sqlite3.connect('Database\\rluDB.db')
        item_=''
             
        with conn :
         cursor = conn.cursor()
        if where_var!="" :
          cursor.execute(query,(str(where_var),))
        else :
          cursor.execute(query)
        data=''
        item=''
        data=cursor.fetchall()
         
        if (data != "[(u'',)]" and data !='[]' and data !='u') :
            for item in data :
                for word in item :
                    item_+=str(word)+'\n'
              
            return item_
			
			
    def deleteFromRlu(self,prodCode) :
        code = str(prodCode)
        conn = sqlite3.connect('Database\\rluDB.db')
		
        with conn :
            cursor = conn.cursor()
            
            cursor.execute("""DELETE from RLU WHERE cod_prod = ? """,(code,))  			
		 


# ################################################END_DB###########################################################




# #################################################ETICHETTE########################################################


    """ Genera un datamatrix a partire dai dati passati come argomento"""
    def dataMatrixGenerator(self,data) :

        encoded = encode(str(data))
        img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels) 
        img.save('dmtx_pass.png')
		
		
    """ Python ZPL2 Library generates ZPL2 code which can be sent to Zebra or similar label printers. The library uses only Millimeter as unit and converts them internally according to printer settings."""		
    def createLabel(self,prodCode,id_radio,printer_s,ip_address,online_printer_success) : 
	
        l = zpl.Label(20,40) # coordinate stampa su video
        height = 0
        l.origin(2,-2) #-1						#l.origin(1,-1) #-1  
        l.write_text("PASS_OK", char_height=2, char_width=2, line_width=47) #40
        l.endorigin()
 
        height += 4
        image_width = 10 
        l.origin((l.width-image_width)/2, 1)			#l.origin((l.width-image_width)/1, 0)
        image_height = l.write_graphic(Image.open(os.path.join(os.path.dirname(zpl.__file__), sys.path[0]+'\dmtx_pass.png')),image_width)
        l.endorigin()

        height = 0
        l.origin(2,-4)							#l.origin(0,-3) #-3.3
        l.write_text(str(prodCode), char_height=5, char_width=2, line_width=46) #41
        l.endorigin()

        height += 3
        l.origin(0.8, -11)								#l.origin(0, -7.5) #-8
        l.write_text(str(id_radio), char_height=3, char_width=2, line_width=59) #60 centrato #50
        l.endorigin()
		
        payload = l.dumpZPL()

        	
        #stampante online o stampante offline
        if online_printer_success :
         
         indirizzo = 'http://'+str(ip_address)+'/pstprnt'
         r=requests.post(indirizzo, payload)
         r=requests.post(indirizzo, payload)
        else :
         
         self.setqueue(str(printer_s))	   
         self.output(payload)
         self.output(payload)

		
		#TODO TESTARE CON ETICHETTE IDONEE
    def createLabelFail(self,prodCode,nack,data_collaudo,id_retry,printer_f,ip_address,online_printer_fail) :
	
        
        l = zpl.Label(50,30) # coordinate stampa su video
        height = 0
        query_sn_GPT = "SELECT sn_gpt FROM RLU WHERE cod_prod = ?"
        serialNumberGPT = MainWindow.select_generica(self,query_sn_GPT,prodCode)
		
        l.origin(5,-6) #-2
        l.write_text("PASS_KO", char_height=2, char_width=2, line_width=60) #40
        l.endorigin()
        	
        if id_retry!=None :
         l.origin(10,-2)
         l.write_text("SCARTATA", char_height=3, char_width=2, line_width=60)
         l.endorigin()
        else :
         l.origin(10,-2)
         l.write_text("FAIL", char_height=3, char_width=2, line_width=60)
         l.endorigin()
		 
        l.origin(5,-9.7)
        l.write_text("S/N : "+str(serialNumberGPT), char_height=3, char_width=2, line_width=60)
        l.endorigin()
 
        
        l.origin(5,-15)
        l.write_text("DATA ULTIMO COLLAUDO", char_height=3, char_width=2, line_width=60) #41
        l.endorigin()
        
        l.origin(5,-18)
        l.write_text(str(data_collaudo), char_height=3, char_width=2, line_width=60)
        l.endorigin()
		
       
        l.origin(5,-22)
        l.write_text("DESCRIZIONE ERRORE", char_height=3, char_width=2, line_width=60) 
        l.endorigin()
		
        l.origin(5,-26)
        l.write_text(str(nack), char_height=3, char_width=2, line_width=60)
        l.endorigin()
		
       
        l.origin(5,-31)
        l.write_text("FIRMA COLLAUDATORE", char_height=3, char_width=2, line_width=60) 
        l.endorigin()
		
        l.origin(5,-38)
        l.write_text("-----------------------------------", char_height=3, char_width=2, line_width=60) 
        l.endorigin()
		
        #¢l.preview()
        payload = l.dumpZPL()
		
        #stampante online o stampante offline
        if online_printer_fail :
         
         indirizzo = 'http://'+str(ip_address)+'/pstprnt'
         r=requests.post(indirizzo, payload)
        else :
         self.setqueue(str(printer_f))	   
         self.output(payload)

        self.sendMail(prodCode,"","collaudo_fallito")
        
		
    
		

    def _output_win(self, commands):
        #if self.queue == 'zebra_python_unittest':
            #print commands
            #return
        hPrinter = win32print.OpenPrinter(self.queue)
        print hPrinter
        try:
            hJob = win32print.StartDocPrinter(hPrinter, 1, ('Label',None,'RAW'))
            try:
                win32print.StartPagePrinter(hPrinter)
                win32print.WritePrinter(hPrinter, commands)
                win32print.EndPagePrinter(hPrinter)
            finally:
                win32print.EndDocPrinter(hPrinter)
        finally:
            win32print.ClosePrinter(hPrinter)

    def output(self, commands):
        """Output EPL2 commands to the label printer

        commands - EPL2 commands to send to the printer
        """
        assert self.queue is not None
        if sys.version_info[0] == 3:
            if type(commands) != bytes:
                commands = str(commands).encode()
        else:
            commands = str(commands).encode()
        
        self._output_win(commands)
      
    

#    def _getqueues_win(self):
#        printers = []
#        for (a,b,name,d) in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
#            printers.append(name)
#        return printers

#    def getqueues(self):
#        """Returns a list of printer queues on local machine"""
#        
#        return self._getqueues_win()
        

    def setqueue(self, queue):
        """Set the printer queue"""
        self.queue = queue

    def setup(self, direct_thermal=None, label_height=None, label_width=None):
        """Set up the label printer. Parameters are not set if they are None.

        direct_thermal - True if using direct thermal labels
        label_height   - tuple (label height, label gap) in dots
        label_width    - in dots
        """
        commands = '\n'
        if direct_thermal:
            commands += ('OD\n')
        if label_height:
           commands += ('Q%s,%s\n'%(label_height[0],label_height[1]))
        if label_width:
            commands += ('q%s\n'%label_width)
        self.output(commands)

    def store_graphic(self, name, filename):
        """Store a .PCX file on the label printer

        name     - name to be used on printer
        filename - local filename
        """
        assert filename.lower().endswith('.pcx')
        commands = '\nGK"%s"\n'%name
        commands += 'GK"%s"\n'%name
        size = os.path.getsize(filename)
        commands += 'GM"%s"%s\n'%(name,size)
        self.output(commands)
        self.output(open(filename,'rb').read())






# ########################################################################################################################





    """ Funzione che gestisce i casi negativi ovvero i nack. In principio gestiva anche gli ack da qui il nome.Controlla la risposta ricevuta ed aggiorna nack o nack_2 nel caso del secondo collaudo. Torna esito fail. """	

    def ack_nack(self,risposta,label,barra,prodCode,rlu_type,id_retry,printer_f,online_printer_fail):
	    
        esito=""
        data_collaudo = self.dateFromTimestamp(prodCode)
        query_ip_ko = "SELECT IP_KO FROM Zebra"
        ip_address = MainWindow.select_generica(self,query_ip_ko,"")
		
        if risposta[:1] == "\x15":
            
            #barra.setStyleSheet(RED_STYLE)
            barra.setStyleSheet('background-color:red')
            label.setStyleSheet('color: red')
        			
        #150100[comando non valido]
        if risposta == "\x15\x01\x00":
             label.setText("comando non valido")
             if id_retry!=None :
              self.update_table_nack_2("comando non valido",prodCode)
             else :
              self.update_table_nack("comando non valido",prodCode)
             self.createLabelFail(prodCode,"comando non valido",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail)
              		  
             esito="fail"
		  #150200[err corrente]
        elif risposta == "\x15\x02\x00":
             label.setText("err misura corrente")
             if id_retry!=None :
              self.update_table_nack_2("err misura corrente",prodCode)
             else :
              self.update_table_nack("err misura corrente",prodCode)
             self.createLabelFail(prodCode,"err misura corrente",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail)			  
             
             esito="fail"
		  #150301[irda_1 ko] 
        elif risposta == "\x15\x03\x01":
             label.setText("test IRDA_1 ko")
             if id_retry!=None :
              self.update_table_nack_2("test IRDA_1 ko",prodCode)
             else :
              self.update_table_nack("test IRDA_1 ko",prodCode)
             self.createLabelFail(prodCode,"test IRDA_1 ko",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail) 			  
             
             esito="fail"  
		  #150302[irda_2 ko]	 
        elif risposta == "\x15\x03\x02":
             label.setText("test IRDA_2 ko")
             if id_retry!=None :
              self.update_table_nack_2("test IRDA_2 ko",prodCode)
             else :
              self.update_table_nack("test IRDA_2 ko",prodCode)
             self.createLabelFail(prodCode,"test IRDA_2 ko",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail)			  
             
             esito="fail"
             
             
		  #150303[irda_1 & irda_2 ko] 
        elif risposta == "\x15\x03\x03":
             label.setText("test IRDA_1,IRDA_2 ko")
             if id_retry!=None :
              self.update_table_nack_2("test IRDA_1,IRDA_2 ko",prodCode)
             else :
              self.update_table_nack("test IRDA_1,IRDA_2 ko",prodCode)
             self.createLabelFail(prodCode,"test IRDA_1,IRDA_2 ko",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail)			   
             
             esito="fail"
		  #150400[test transceiver err] 	 
        elif risposta == "\x15\x04\x00":
             label.setText("test transceiver non riuscito")
             
             if id_retry!=None :
              self.update_table_nack_2("test transceiver non riuscito",prodCode)
             else :
              self.update_table_nack("test transceiver non riuscito",prodCode)
             self.createLabelFail(prodCode,"err test trans",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail)
			  
             esito="fail"
		  #150500[test EEPROM err] 
        elif risposta == "\x15\x05\x00":
             label.setText("test EEPROM non riuscito")
             
             if id_retry!=None :
              self.update_table_nack_2("test EEPROM non riuscito",prodCode)
              
             else :
               self.update_table_nack("test EEPROM non riuscito",prodCode)
             self.createLabelFail(prodCode,"err EEPROM",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail)
             
             esito="fail"
		  #150600[Test Key err]
        elif risposta == "\x15\x06\x00":
             label.setText("test KEY non riuscito")
             
             if id_retry!=None :
              self.update_table_nack_2("test KEY non riuscito",prodCode)
              
             else :
              self.update_table_nack("test KEY non riuscito",prodCode)
             self.createLabelFail(prodCode,"err test KEY",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail)
             
             esito="fail"  
        #150700[corrente out of range]			 
        elif risposta == "\x15\x07\x00":
             label.setText("corrente out of range")
             
             if id_retry!=None :
              self.update_table_nack_2("corrente out of range",prodCode)             
             else :              
              self.update_table_nack("corrente out of range",prodCode)
             self.createLabelFail(prodCode,"corrente out of range",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail)
             
             esito="fail"
		  #150800[rssi out of range]
        elif risposta == "\x15\x08\x00":
             label.setText("rssi out of range")
             
             if id_retry!=None :
              self.update_table_nack_2("rssi out of range",prodCode)
             else :
              self.update_table_nack("rssi out of range",prodCode)
             self.createLabelFail(prodCode,"rssi out of range",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail)
			 
             esito="fail"   
		  #151500[generico]
        else :
             label.setText("errore generico, comunicazione interrotta")
            
             if id_retry!=None :
              self.update_table_nack_2("errore generico",prodCode)
             else :
              self.update_table_nack("errore generico",prodCode)
             self.createLabelFail(prodCode,"err generico",data_collaudo,id_retry,printer_f,ip_address,online_printer_fail)
			 
             esito="fail"
			
        return esito       


    #in risposta mi aspetto FIRMWARE_VERSION 
    # impostare condizione che se RLU-B 550200 altrimenti 550100
    def abilita_programmazione(self, tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail):
        esito=""	
        command =""
        command_=""
        command_r=""
        risposta_ex=""
        barra = self.progressBar_2
        barra.reset()
        secondi = 60.0000000000
        label = self.labelBar_1
        text = "programmazione on"
        
        if rlu_type == 'RLU_B' :
         command_ = "550200" #0x550200 per RLU-B  550100 per RLU
        else :
         command_ = "550100"
		 
        command = command_.decode("hex")
        
        risposta = self.write_read_serial(command,secondi,barra,label,text)
        
        risposta_ex = risposta.encode("hex")
        try :
         fw_version1 = str(int(risposta_ex[2:-2], 16)) #hw version base 10
         fw_version2 = str(int(risposta_ex[-2:], 16)) #sw version base_10
         fw_version = fw_version1+fw_version2
         command_r = risposta_ex[:2] #comando 50
        except Exception, e :
         print "nessuna risposta : "+str(e)
        
        #print ('sw : ' + fw_version)
       # print ('cmd : ' + command_r)
		
        tentativi+=1

        if command_r == "50" :
           if id_retry != None :
            self.update_table_ack_2("ok_prog",prodCode) # update campo ack_2 se device ricollaudato
            self.update_table_fw(fw_version,prodCode) #update fw_version
           else :			
            
            self.update_table_ack("ok_prog",prodCode) #update campo ack
            self.update_table_fw(fw_version,prodCode) #update fw_version
			
           label.setStyleSheet("color:green")
           label.setText("programmazione ok")
           barra.setValue(secondi)
           self.progressBar.setValue(20)
           
        else :
           if tentativi==1 :
              
              
              esito=self.abilita_programmazione(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
           else :
              esito=self.ack_nack(risposta,label,barra,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
              barra.setValue(secondi)#100%
			  
        return esito     
           

    #in risposta ACK/NACK : 
    def disabilita_programmazione(self, tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail):
        esito=""
        barra = self.progressBar_3
        secondi = 20.0000000000
        label = self.labelBar_2
        text = "programmazione off"
        
        command_ = "560000"
        command = command_.decode("hex")
        risposta = self.write_read_serial(command,secondi,barra,label,text)
        tentativi+=1
        if risposta == "\x06\x00\x00":
            if id_retry != None :
             self.update_table_ack_2("ok_disab",prodCode) # update campo ack_2 se device ricollaudato
            else :			
             self.update_table_ack("ok_disab",prodCode) # update al primo collaudo
            label.setStyleSheet("color:green")
            label.setText("prog disabilitata")
            #self.progressBar.setValue(28.57142857142857)
            
            barra.setValue(secondi)
            self.progressBar.setValue(40)
        else :
           if tentativi==1 :
              
              
              esito=self.disabilita_programmazione(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
           else :
              esito=self.ack_nack(risposta,label,barra,type,id_retry,printer_f,online_printer_fail)
              barra.setValue(secondi)
			  
        return esito
              

    def test_irda2(self, tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail):
        esito=""
        barra = self.progressBar_4
        secondi = 50.0000000000
        label = self.labelBar_3
        text = "test irda2"
        command_ = "570000"
        command = command_.decode("hex")
        risposta = self.write_read_serial(command,secondi,barra,label,text)
        tentativi+=1
        if risposta == "\x06\x00\x00":
            if id_retry != None :
             self.update_table_ack_2("ok_irda2",prodCode) # update campo ack_2 se device ricollaudato
            else :			
             self.update_table_ack("ok_irda2",prodCode) # update al primo collaudo
            label.setStyleSheet("color:green")
            label.setText("irda2_ok")
            #self.progressBar.setValue(28.57142857142857)
            
            barra.setValue(secondi)
            self.progressBar.setValue(60)
        else :
           if tentativi==1 :
              
              
              esito=self.test_irda2(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
              
           else :
              esito=self.ack_nack(risposta,label,barra,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
              barra.setValue(secondi)
              
             
        return esito

		
    def get_key(self, tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail):
        esito=""
        barra = self.progressBar_5
        secondi = 30.0000000000
        label = self.labelBar_4
        text = "get key"
        command_ = "590000"
        command = command_.decode("hex")
        risposta = self.write_read_serial(command,secondi,barra,label,text)
        risposta_ex = risposta.encode("hex") #la funz ser.readline() torna un ASCII che riconverto in hex
        key = risposta_ex[2:-2]#
        command_r = risposta_ex[:2] #comando 59
        
     		
        tentativi+=1
        if command_r == "59":
            if id_retry != None :
             self.update_table_ack_2("ok_key",prodCode) # update campo ack_2 se device ricollaudato
             self.update_table_key(key,prodCode)
            else :			
             self.update_table_ack("ok_key",prodCode) # update al primo collaudo
             self.update_table_key(key,prodCode)
            label.setStyleSheet("color:green")		
            label.setText("key ok")
            barra.setValue(secondi)
            
            self.progressBar.setValue(80)
        else :
           if tentativi==1 :
              
             
              esito=self.get_key(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
           else :
              esito=self.ack_nack(risposta,label,barra,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
              barra.setValue(secondi)
			  
        return esito
			
		#torna il seriale che devo salvare nel DB (manca questa parte) e l'RSSI che se < 240 considero NACK
    def test_transceiver(self, tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail):
        esito=""
        barra = self.progressBar_6
        secondi = 30.0000000000
        label = self.labelBar_5
        text = "test transceiver"
        command_ = "580000"
        command = command_.decode("hex")
    	
        risposta = self.write_read_serial(command,secondi,barra,label,text) #ascii
        #la funz ser.readline() torna un ASCII che riconverto in hex
        risposta_ex = risposta.encode("hex") #58d735bb7617100133c 
        id_radio = risposta_ex[2:-2]#seriale es d735bb761710013
        rssi = risposta_ex[-2:] #RSSI es c3
        rssi_10 = int(rssi, 16) #RSSI base 10
        tentativi+=1
        if risposta != "\x15\x04\x00":
            if(rssi_10 >= 220) :             #170 x debug 240 default
              if id_retry != None :
               self.update_table_ack_2("ok_trans",prodCode) # update campo ack_2 se device ricollaudato
               self.update_table_id_radio(id_radio,prodCode) #update id_radio
              else :			
               self.update_table_ack("ok_trans",prodCode) # update al primo collaudo
               self.update_table_id_radio(id_radio,prodCode) #update id_radio
			   
              label.setStyleSheet("color:green")
              label.setText("trans ok")
              barra.setValue(secondi)
              self.progressBar.setValue(100)
            else :
              if tentativi==1 :
               
               esito=self.test_transceiver(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
              else :
               esito=self.ack_nack("\x15\x08\x00",label,barra,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
               barra.setValue(secondi)
        else :
            if tentativi==1 :
              
              
              esito=self.test_transceiver(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
            else :
              esito=self.ack_nack(risposta,label,barra,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
              barra.setValue(secondi)
           
        return esito
			
   #torna la corrente che se < 32 considero come NACK
    def misura_corrente_ricarica(self, tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail):
        esito=""
        barra = self.progressBar_7
        secondi = 40.0000000000
        label = self.labelBar_6
        text = "test corrente"

        command_ = "660000"
        command = command_.decode("hex") #lo converto in hex per inviarlo 
        risposta = self.write_read_serial(command,secondi,barra,label,text)   
		
        risposta_ex = risposta.encode("hex") #la funz ser.readline() torna un ASCII che riconverto in hex
        corrente = risposta_ex[2:] #ultimi 2 byte con la corrente
        corrente_10 = int(corrente, 16) #valore in base 10 per fare confronti
        
        
        #print ('risp_ex : ' + risposta_ex)
        #print ('corrente_10 : ' + str(corrente_10))
        
        tentativi+=1
        if risposta != "\x15\x02\x00":
           if(corrente_10 >= 32) :
              if id_retry != None :
               self.update_table_ack_2("ok_corrente",prodCode) # update campo ack_2 se device ricollaudato
              else :			
               self.update_table_ack("ok_corrente",prodCode) # update al primo collaudo
              label.setStyleSheet("color:green")
              label.setText("corrente ok")
              barra.setValue(secondi)
              self.progressBar.setValue(20)
           else :
              if tentativi==1 :
               
               esito=self.misura_corrente_ricarica(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
              else :
               esito=self.ack_nack("\x15\x07\x00",label,barra,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
               barra.setValue(secondi)  
             
        else :
           if tentativi==1 :
              
              esito=self.misura_corrente_ricarica(tentativi,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
           else :
              esito=self.ack_nack(risposta,label,barra,prodCode,rlu_type,id_retry,printer_f,online_printer_fail)
              barra.setValue(secondi)
			  
        return esito

    def echo(self):
        stato=False
        #barra = self.progressBar_8
        secondi = 2.0000000000
        label = self.labelBar_7
        #barra.setValue(0)
        label.setStyleSheet("color:black")
        text = "attendere..."

        command_ = "0F0000" #0x13 o 0x16 etc
        command = command_.decode("hex")
        risposta = self.write_read_serial(command,secondi,None,label,text)
		
        if risposta == command :
		
            label.setStyleSheet("color:green")
            label.setText( "Connection ok")  
            stato=True
        elif risposta == "" :
		
            label.setStyleSheet("color:red")
            label.setText("no connection") 
            stato=False
        else :
            
            label.setStyleSheet("color:red")
            label.setText("errore")
            stato=False
			
        return stato

    #controlla la selezione della porta COM sulla combobox 
    def onChangedCom(self, text):
      com_port_number = text 
      #print "com changed : "+	com_port_number  
      return com_port_number  
 
    

	# Cicla per 'n' secondi, quando riceve una risposta la salva nella variabile per il return.
	#termina in ogni caso il ciclo di 'n' secondi così da non interrompere le animazioni della barra.
	
    def write_read_serial(self,command,secondi,barra,label,text) :
            #fondamentale per evitare il freeze della GUI
            gui=QtGui.QApplication.processEvents
			   #numero di porta COM selezionato dalla combobox
            com_port_number=self.COM_edit.activated[str].connect(self.onChangedCom)
			   #numero di porta COM di default caricato per primo nella combobox senza che l'utente interagisca
            com_port_number=self.COM_edit.currentText()
            #print "porte com : "+str(com_port_number)
			   
            ser.port = str(com_port_number)
            resp=''
            if (com_port_number!='') :
            
          
					try:
						ser.close()
						time.sleep(1)
						ser.open()
							
						
					except Exception, e:
						print "error open serial port: " + str(e)
						#exit()
					if ser.isOpen():

						try:
							ser.flushInput()
							ser.flushOutput()
							#write data
							ser.write(command)
							
							
							if command =='U\x02\x00': # avvio in concomitanza l'installazione del nuovo FW
							 label.setText("waiting..")
							 self.programma_fw()
							startTime = time.time()                    
							#label.setText("ATTENDERE "+ str(secondi)[:2] +" SECONDI PER LA RISPOSTA...")
							label.setStyleSheet('color:black')
							label.setText(text)
							while time.time()-startTime <= secondi :
								#fondamentale per evitare il freeze della GUI
								gui()
								response = ser.readline()
								if barra!= None :
								 barra.setValue(time.time()-startTime)
								#print ("resp : "+response,)

								if (response!=''):
								 
								 resp += response
								 
								 
								 time.sleep(3)
								 break
								 
								
							ser.close()
							if(response=='') :
							 label.setText("cdc non risponde: riprova ")
							 label.setStyleSheet("color:red")
                       		
					   
						except Exception, e1:
							print "error communicating...: " + str(e1)

					else:
						print "cannot open serial port "
            return resp





# ################################################################################ PROCEDURA PROGRAMMAZIONE FIRMWARE ###############################################################################

    

    
		
		




############################################################################################################################
###########################################INSERIMENTO ID E CHIAVE NEL DB AZURE#############################################
############################################################################################################################

#  AUTOMATIZZATA CIOè DOPO COLLAUDO, IN CASO DI SUCCESSO, SALVA QUESTE INFO SUL DB AZURE
# 



    def return_bytes(self,the_bytes):
     return the_bytes
	 
	 
# se gia inserito faccio update altrimenti insert
    def citymonitorDB(self,id_radio,conn_string): 	
     server = 'citymonitoreu.database.windows.net'
     database = 'citymonitor2'
     username = 'citymonitor_dbadmin@citymonitoreu'
     password = 'MonitCityMenoWatt1296'
     driver= '{SQL Server}'
     conn = pyodbc.connect('DRIVER='+driver+';SERVER='+server+';PORT=1433;DATABASE='+database+';UID='+username+';PWD='+ password)

     cursor = conn.cursor()

     conn.add_output_converter(-155, self.return_bytes) #!FONDAMENTALE! ALTRIMENTI ERRORE

     query_insert = '''
                INSERT INTO [DevicesLightPointsTemp] (ID, CONN_STRING)
                VALUES
                (?,?)
                '''
     query_select = '''select ID from [DevicesLightPointsTemp] where ID=?'''
     query_update = '''update [DevicesLightPointsTemp] set ID=?,CONN_STRING=? where ID=?'''
	 
     
     cursor.execute(query_select,(id_radio),)  
     data = cursor.fetchall() 
	 
     if data!=[] :
      cursor.execute(query_update,(id_radio),(conn_string),(id_radio),)  
     else :
      cursor.execute(query_insert,(id_radio),(conn_string),)  
	  
     conn.commit()				
     cursor.close()
     conn.close()





   
   


class RluRluB(QtGui.QMainWindow,Ui_rlu_rlub):

    import win32print
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self)
        Ui_rlu_rlub.__init__(self)
        self.setupUi(self)
		
class RluRluB_again(QtGui.QMainWindow,Ui_rlu_rlub_again):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self)
        Ui_rlu_rlub_again.__init__(self)
        self.setupUi(self)		

class NewOld(QtGui.QMainWindow,Ui_new_old):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self)
        Ui_new_old.__init__(self)
        self.setupUi(self)		

#avviata come prima finestra è un container
class MainWindow(QtGui.QMainWindow,Ui_new_old):
    #funzioni per impostare il layout
    def __init__(self, parent=None):
        
        QtGui.QMainWindow.__init__(self)
        Ui_new_old.__init__(self)
        self.setupUi(self)
	 ###########################################
        super(MainWindow, self).__init__(parent)
        self.setFixedSize(1300, 1000)
        
        self.startNewOld()# avvia questa come "home"
        #self.startRluRluB()

    def startNewOld(self):
        
        self.NewOld = NewOld(self)
        self.setWindowTitle("Facere")
        self.setCentralWidget(self.NewOld)
        
        try:
		   #test connessione internet
         if urllib2.urlopen('http://216.58.192.142', timeout=1) :
          #test connessione al DB CM 
          try :
           
           #session = ftplib.FTP('94.177.203.9','metering','m3t3r1ng_01')
           #session.cwd('/Facere/')
           #file = open('Database\\rluDB.db','rb')
           #session.storbinary('STOR '+ 'rluDB.db', file)
           #file.close()
           #session.quit()
              
           rc=os.system("powershell -Command echo ((new-object Net.Sockets.TcpClient).Client.Connect('citymonitoreu.database.windows.net', 1433))") #rc=0->ok,rc=1->ko
           if rc != 1 :
            self.NewOld.NewButton.clicked.connect(self.startRluRluB) # clicco e avvia la finestra di scelta
            self.NewOld.OldButton.clicked.connect(self.startRluRluB_again) # clicco e avvia la finestra di scelta
            self.show()
           else :
            MyApp.createMessageBox(self,"connessione al DB  non riuscita","ERRORE","impossibile avviare Facere")
            sys.exit(0)
           
          except Exception, e :
           MyApp.createMessageBox(self,"connessione al DB  non riuscita","ERRORE","impossibile avviare Facere")
           sys.exit(0)
        except urllib2.URLError as err:
         MyApp.createMessageBox(self,"connessione internet assente","ERRORE","impossibile avviare Facere")
         sys.exit(0)
        
        		 
  #def upload_oracolo_false():
# time.sleep(20) #TBD
 
# with open(path,'w') as file :
#     file.write('false')

 #session = FTP('94.177.203.9','metering','m3t3r1ng_01')
 #session.cwd('/'+sys_title+'/')
 #file = open('oracolo.txt','rb')
 #session.storbinary('STOR '+ 'oracolo.txt', file)
 #file.close()
 #session.quit()
 #print 'oracolo impostato a -false-'       
        
		
	#torna una lista di ID prelevati dal DB i quali avevano precedetemente fallito il collaudo
    def show_id_for_retry(self,rlu_type): #rlu_type
        
        conn = sqlite3.connect('Database\\rluDB.db')
        #cast a string altrimenti in questo caso non gli piace
       
        type=str(self.rlu_type)
        with conn :
         cursor = conn.cursor()
         #cursor.execute("SELECT cod_prod FROM RLU WHERE failed='true' and (nack_2 is null or nack_2 ='') and (ack_2 is null or ack_2 ='') and type=?",(type,))
         cursor.execute("SELECT sn_gpt FROM RLU WHERE (ack_2 == '' and nack_2=='' and nack<>'') and type=?",(type,)) 
         data =[]
         lista_id=[]
          
         data.append(cursor.fetchall())
         
         
         if (data != "[(u'',)]" and data !='[]') :
            for item in data :
                
                for word in item :
                    if (word != "") :
                        
                        #lista_nack.append(word[0])
                        lista_id.append(word[0])
     
         return lista_id                   
        
    @staticmethod 
    def select_generica(self,query,where_var):
        conn = sqlite3.connect('Database\\rluDB.db')
             
        with conn :
         cursor = conn.cursor()
        if where_var!="" :
          cursor.execute(query,(str(where_var),))
        else :
          cursor.execute(query)
        data=''
        item=''
        data=cursor.fetchall()
         
        if (data != "[(u'',)]" and data !='[]') :
            for item in data :
                for word in item :
                    if (word != "") :
                        
                        item=word
     
        return item                 	

    #avvia la finestra rlu-rlub
    def startRluRluB(self):
        self.Window = RluRluB()
        self.setWindowTitle("Facere")
        self.setCentralWidget(self.Window)
		
  		  #al click del pulsante "ok" avviao la main win chiamata Myapp
        self.Window.pushButton.clicked.connect(self.startMyApp) # ok
        
        #lista 
        list1 = [('RLU'),('RLU_B'),]
        list_hw = [('0'),('1'),('2'),('3'),('4'),('5'),('6'),('7'),('8'),('9'),('A'),('B'),('C'),('D'),('E'),('F'),('G'),('H'),('I'),('J'),('K'),('L'),('M'),('N'),('O'),('P'),('Q'),('R'),('S'),('T'),('U'),('V'),('W'),('X'),('Y'),('Z'),]
		  #pulisco poi popolo la lista
        self.Window.comboBox.clear()
        self.Window.comboBox.addItems(list1)
        
        #pulisco poi popolo la lista hw
        self.Window.comboBox_hw.clear()
        self.Window.comboBox_hw.addItems(list_hw)
		
        #pulisco poi popolo la lista hw
        self.Window.comboBox_pc.clear()
        self.Window.comboBox_pc.addItems(list_hw)
       
        
        #al cambio elemento nella combobox assegna il valore alla variabile
        self.rlu_type=self.Window.comboBox.activated[str].connect(self.onChanged)
        #assegna il valore statico alla variabile, cioè se non cambio e lascio quello di default 
        self.rlu_type=self.Window.comboBox.currentText()
		  #hw version selezione
        self.hw_version=self.Window.comboBox_hw.activated[str].connect(self.onChanged_hw)
        self.hw_version=self.Window.comboBox_hw.currentText()
        
        # selezione produzione e collaudo
        self.pc_version=self.Window.comboBox_pc.activated[str].connect(self.onChanged_pc)
        self.pc_version=self.Window.comboBox_pc.currentText()
		
        #al cambio elemento nella spinbox assegna il valore alla variabile
        self.numDevice=self.Window.spinBox.valueChanged[str].connect(self.valueChange)
		  #assegna il valore statico alla variabile, cioè se non cambio e lascio quello di default
        self.numDevice=self.Window.spinBox.value()
		
        
        self.serialNumberGPT = self.Window.Button_sn.clicked.connect(self.getSN)
		
		  # #########################################ZEBRA PRINTER SETUP ###############################################
		  
         # riempio la lista con le stampantizebra  installate attualmente  sul pc
        zebra_printers=[]
        list_printers = self.getqueues()
        for item in list_printers :
          
		     if item[0] == 'Z' :
		      zebra_printers.append(item)
        
		  #pulisco poi popolo la lista
        self.Window.comboBox_z_fail.clear()
        self.Window.comboBox_z_fail.addItems(zebra_printers)
		
        self.Window.comboBox_z_success.clear()
        self.Window.comboBox_z_success.addItems(zebra_printers)
		
        self.printer_s=self.Window.comboBox_z_success.activated[str].connect(self.onChanged_printer)
        self.printer_s=self.Window.comboBox_z_success.currentText()
		
        self.printer_f=self.Window.comboBox_z_fail.activated[str].connect(self.onChanged_printer_f)
        self.printer_f=self.Window.comboBox_z_fail.currentText()
		
        self.Window.Button_prova_success.clicked.connect(lambda:self.createLabel_test(self.printer_s))
        self.Window.Button_prova_fail.clicked.connect(lambda:self.createLabelFail_test(self.printer_f))
		
		  # #################################### ZEBRA IP CONFIGURATIONS ##############################################
		  
		  #spunta sulla checkbox che abilita l'inserimento degli IP  nel DB. Con la checkbox true, online_printer=true
        
        self.online_printer_success=self.Window.checkBox.stateChanged.connect(self.toggleGroupBox_success)
        self.online_printer_fail=self.Window.checkBox_2.stateChanged.connect(self.toggleGroupBox_fail)
        
        #al click sul pulsante aggiorno il/gli IP nel DB
        self.Window.Button_z.clicked.connect(self.updateIpValues)
		
		  
		
        
		

        #altrimenti crasha
        self.serial = None
        self.id_retry = None
        self.nack = None
        
        self.show()
		
	#avvia la finestra rlu-rlub AGAIN ovvero i device da collaudare nuovamente poiche avevano ricevuto NACK
	
    def startRluRluB_again(self): #rlu_type
        self.Window = RluRluB_again()
        self.setWindowTitle("Facere")
        self.setCentralWidget(self.Window)
		
        #lista 
        list1 = [('RLU_B'),('RLU'),]
		  #pulisco poi popolo la lista
        self.Window.comboBox.clear()
        self.Window.comboBox.addItems(list1)
       
        
        #al cambio elemento nella combobox assegna il valore alla variabile
        self.rlu_type=self.Window.comboBox.activated[str].connect(self.onChanged_again)
        #assegna il valore statico alla variabile, cioè se non cambio e lascio quello di default 
        self.rlu_type=self.Window.comboBox.currentText()
		
		  ###############################COMBOBOX_ID_E_NACK_PER_RETRY################################	
        lista_id=[]
        #salvo nella lista gli ID dei device da ricollaudare
        lista_id=self.show_id_for_retry(self.rlu_type) 
		  #aggiungo questi device alla combobox in modo da poterli selezionare
        #self.Window.comboBox_2.clear()
        self.Window.comboBox_2.addItems(lista_id)	
        
        #il primo elemento così è vuoto e solo selezionando si riempie la label indicante il NACK
       # self.Window.comboBox_2.addItems(" ",)
        
		  #al cambio elemento nella combobox assegna il valore alla variabile
        self.serialNumberGPT=self.Window.comboBox_2.activated[str].connect(self.onChanged_idForRetry)
		
		  #assegna il valore statico alla variabile, cioè se non cambio e lascio quello di default
        self.serialNumberGPT=self.Window.comboBox_2.currentText()
        #in questo modo riempio la label con il nack corrispondente all'ID gia presente nella combobox di default
		  #senza che l'utente ci interagisca per intenderci
        
        if str(self.serialNumberGPT)!="" and str(self.serialNumberGPT)!=None :
         query_nack = "SELECT nack FROM RLU WHERE (ack_2 == '' and nack_2=='' and nack<>'') and sn_gpt = ?"
         self.nack=self.select_generica(self,query_nack,self.serialNumberGPT)
         self.Window.label_nack.setText(str(self.nack))
		 
         query_mnw="SELECT cod_prod FROM RLU where sn_gpt = ?"
         self.id_retry=self.select_generica(self,query_mnw,self.serialNumberGPT)
         self.Window.label_codprod.setText(str(self.id_retry))
		
	     # ################################COMBOBOX RLU/RLU_B#########################################
		 
		 
		  # #########################################ZEBRA PRINTER SETUP ###############################################

        # riempio la lista con le stampantizebra  installate attualmente  sul pc
        zebra_printers=[]
        list_printers = self.getqueues()
        for item in list_printers :
          
		     if item[0] == 'Z' :
		      zebra_printers.append(item)
        
		  #pulisco poi popolo la lista
        self.Window.comboBox_z_fail_a.clear()
        self.Window.comboBox_z_fail_a.addItems(zebra_printers)
		
        self.Window.comboBox_z_success_a.clear()
        self.Window.comboBox_z_success_a.addItems(zebra_printers)
		
        self.printer_s=self.Window.comboBox_z_success_a.activated[str].connect(self.onChanged_printer)
        self.printer_s=self.Window.comboBox_z_success_a.currentText()
		
        self.printer_f=self.Window.comboBox_z_fail_a.activated[str].connect(self.onChanged_printer_f)
        self.printer_f=self.Window.comboBox_z_fail_a.currentText()
		
        self.Window.Button_prova_success.clicked.connect(lambda:self.createLabel_test(self.printer_s))
        self.Window.Button_prova_fail.clicked.connect(lambda:self.createLabelFail_test(self.printer_f))
		
        # #################################### ZEBRA IP CONFIGURATIONS ##############################################
		  
		  #spunta sulla checkbox che abilita l'inserimento degli IP  nel DB. Con la checkbox true, online_printer=true
        
        self.online_printer_success=self.Window.checkBox_a.stateChanged.connect(self.toggleGroupBox_success_a)
        self.online_printer_fail=self.Window.checkBox_2_a.stateChanged.connect(self.toggleGroupBox_fail_a)
        
        #al click sul pulsante aggiorno il/gli IP nel DB
        self.Window.Button_z_a.clicked.connect(self.updateIpValues_a)
		
		 
		
		  #al click del pulsante "ok" avvio la main win chiamata Myapp
        self.Window.pushButton.clicked.connect(self.startMyApp) # ok
        
        self.hw_version=None  
        self.pc_version=None
        #self.serialNumberGPT=None
        
		  #altrimenti crasha, in questo modo trattandosi di un retry, dovrò collaudare un solo dispositivo
        self.numDevice = 1
        
        self.show()
		
		
    def _output_win(self, commands):
        #if self.queue == 'zebra_python_unittest':
            #print commands
            #return
        hPrinter = win32print.OpenPrinter(self.queue)
        print hPrinter
        try:
            hJob = win32print.StartDocPrinter(hPrinter, 1, ('Label',None,'RAW'))
            try:
                win32print.StartPagePrinter(hPrinter)
                win32print.WritePrinter(hPrinter, commands)
                win32print.EndPagePrinter(hPrinter)
            finally:
                win32print.EndDocPrinter(hPrinter)
        finally:
            win32print.ClosePrinter(hPrinter)

    def output(self, commands):
        """Output EPL2 commands to the label printer

        commands - EPL2 commands to send to the printer
        """
        assert self.queue is not None
        if sys.version_info[0] == 3:
            if type(commands) != bytes:
                commands = str(commands).encode()
        else:
            commands = str(commands).encode()
        
        self._output_win(commands)
      
    

#    def _getqueues_win(self):
#        printers = []
#        for (a,b,name,d) in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
#            printers.append(name)
#        return printers

#    def getqueues(self):
#        """Returns a list of printer queues on local machine"""
#        
#        return self._getqueues_win()
        

    def setqueue(self, queue):
        """Set the printer queue"""
        self.queue = queue

    def setup(self, direct_thermal=None, label_height=None, label_width=None):
        """Set up the label printer. Parameters are not set if they are None.

        direct_thermal - True if using direct thermal labels
        label_height   - tuple (label height, label gap) in dots
        label_width    - in dots
        """
        commands = '\n'
        if direct_thermal:
            commands += ('OD\n')
        if label_height:
           commands += ('Q%s,%s\n'%(label_height[0],label_height[1]))
        if label_width:
            commands += ('q%s\n'%label_width)
        self.output(commands)

    def store_graphic(self, name, filename):
        """Store a .PCX file on the label printer

        name     - name to be used on printer
        filename - local filename
        """
        assert filename.lower().endswith('.pcx')
        commands = '\nGK"%s"\n'%name
        commands += 'GK"%s"\n'%name
        size = os.path.getsize(filename)
        commands += 'GM"%s"%s\n'%(name,size)
        self.output(commands)
        self.output(open(filename,'rb').read())
		
    def createLabel_test(self,printer_s) : 
	
        l = zpl.Label(20,40) # coordinate stampa su video
        height = 0
        l.origin(2,-2) #-1						#l.origin(1,-1) #-1  
        l.write_text("PASS_OK", char_height=2, char_width=2, line_width=47) #40
        l.endorigin()
 
        height += 4
        image_width = 10 
        l.origin((l.width-image_width)/2, 1)			#l.origin((l.width-image_width)/1, 0)
        image_height = l.write_graphic(Image.open(os.path.join(os.path.dirname(zpl.__file__), sys.path[0]+'\dmtx_pass.png')),image_width)
        l.endorigin()

        height = 0
        l.origin(2,-4)							#l.origin(0,-3) #-3.3
        l.write_text(str("00X"), char_height=5, char_width=2, line_width=46) #41
        l.endorigin()

        height += 3
        l.origin(0.8, -11)								#l.origin(0, -7.5) #-8
        l.write_text(str("d7352174db180102"), char_height=3, char_width=2, line_width=59) #60 centrato #50
        l.endorigin()
		
        payload = l.dumpZPL()

        self.setqueue(str(printer_s))	   
        self.output(payload)
		
		
    def createLabelFail_test(self,printer_f) :
	
        
        l = zpl.Label(50,30) # coordinate stampa su video
        height = 0
        
        serialNumberGPT = "SN000000000"
		
        l.origin(5,-6) #-2
        l.write_text("PASS_KO", char_height=2, char_width=2, line_width=60) #40
        l.endorigin() 	
		
        l.origin(10,-2)
        l.write_text("FAIL", char_height=3, char_width=2, line_width=60)
        l.endorigin()

        l.origin(5,-9.7)
        l.write_text("S/N : "+str(serialNumberGPT), char_height=3, char_width=2, line_width=60)
        l.endorigin()
        
        l.origin(5,-15)
        l.write_text("DATA ULTIMO COLLAUDO", char_height=3, char_width=2, line_width=60) #41
        l.endorigin()
        
        l.origin(5,-18)
        l.write_text(str("4/10/2019 - 17:30"), char_height=3, char_width=2, line_width=60)
        l.endorigin()
	  
        l.origin(5,-22)
        l.write_text("DESCRIZIONE ERRORE", char_height=3, char_width=2, line_width=60) 
        l.endorigin()
		
        l.origin(5,-26)
        l.write_text(str("rssi out of range"), char_height=3, char_width=2, line_width=60)
        l.endorigin()
	
        l.origin(5,-31)
        l.write_text("FIRMA COLLAUDATORE", char_height=3, char_width=2, line_width=60) 
        l.endorigin()
		
        l.origin(5,-38)
        l.write_text("-----------------------------------", char_height=3, char_width=2, line_width=60) 
        l.endorigin()
	
        payload = l.dumpZPL()
        self.setqueue(str(printer_f))	   
        self.output(payload)

        
		
	#controllo che il seriale non sia vuoto e non sia uguale a quello di un device già collaudato	
    def getSN(self):
	     
        query_seriale = 'SELECT sn_gpt FROM RLU WHERE sn_gpt =?'
        try :
         self.serialNumberGPT= self.Window.lineEdit_sn.text()
         serialeDB=self.select_generica(self,query_seriale,self.serialNumberGPT)
		 
         if self.serialNumberGPT != "" and self.serialNumberGPT != serialeDB :
          self.Window.label_sn.setStyleSheet('color:green')
          self.Window.label_sn.setText("seriale idoneo")
          self.Window.pushButton.setEnabled(True)
          return self.serialNumberGPT
         else :
          self.Window.label_sn.setStyleSheet('color:red')
          self.Window.label_sn.setText("seriale mancante o collaudato")
        except  :
         self.Window.label_sn.setStyleSheet('color:red')
         self.Window.label_sn.setText("seriale mancante o collaudato")		
         
   #popolo la lista deille stampanti installate sul pc, sopra faccio dei controlli per visualizzare solo le Zebra
    def _getqueues_win(self):
        printers = []
        for (a,b,name,d) in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
            printers.append(name)
        return printers

    def getqueues(self):
        """Returns a list of printer queues on local machine"""
        
        return self._getqueues_win()
	
# alla spunta abilito l'inserimento della stampante in rete e disabilito quella offline	
    def toggleGroupBox_success(self,state):
        if state > 0:
         self.Window.label_z_success.setEnabled(True)
         self.Window.lineEdit_z_success.setEnabled(True)
         self.Window.label_z_success_usb.setEnabled(False)
         self.Window.comboBox_z_success.setEnabled(False)
         
         self.Window.Button_z.setEnabled(True)
         
         self.online_printer_success = True
         return self.online_printer_success
        else:
         
         self.Window.lineEdit_z_success.setEnabled(False)
         self.Window.label_z_success.setEnabled(False)
		 
         self.Window.label_z_success_usb.setEnabled(True)
         self.Window.comboBox_z_success.setEnabled(True)
         
         self.Window.Button_z.setEnabled(False)
		 
    def toggleGroupBox_fail(self,state):
        if state > 0:
         self.Window.label_z_fail.setEnabled(True)
         self.Window.lineEdit_z_fail.setEnabled(True)
         self.Window.label_z_fail_usb.setEnabled(False)
         self.Window.comboBox_z_fail.setEnabled(False)
         
         self.Window.Button_z.setEnabled(True)
         
         self.online_printer_fail = True
         return self.online_printer_fail
        else:
         
         self.Window.lineEdit_z_fail.setEnabled(False)
         self.Window.label_z_fail.setEnabled(False)
		 
         self.Window.label_z_fail_usb.setEnabled(True)
         self.Window.comboBox_z_fail.setEnabled(True)
         
         self.Window.Button_z.setEnabled(False)
		 
    def toggleGroupBox_success_a(self,state):
        if state > 0:
         self.Window.label_z_success_a.setEnabled(True)
         self.Window.lineEdit_z_success_a.setEnabled(True)
         self.Window.label_z_success_usb_a.setEnabled(False)
         self.Window.comboBox_z_success_a.setEnabled(False)
         
         self.Window.Button_z_a.setEnabled(True)
         
         self.online_printer_success = True
         return self.online_printer_success
        else:
         
         self.Window.lineEdit_z_success_a.setEnabled(False)
         self.Window.label_z_success_a.setEnabled(False)
		 
         self.Window.label_z_success_usb_a.setEnabled(True)
         self.Window.comboBox_z_success_a.setEnabled(True)
         
         self.Window.Button_z_a.setEnabled(False)
		 
    def toggleGroupBox_fail_a(self,state):
        if state > 0:
         self.Window.label_z_fail_a.setEnabled(True)
         self.Window.lineEdit_z_fail_a.setEnabled(True)
         self.Window.label_z_fail_usb_a.setEnabled(False)
         self.Window.comboBox_z_fail_a.setEnabled(False)
         
         self.Window.Button_z_a.setEnabled(True)
         
         self.online_printer_fail = True
         return self.online_printer_fail
        else:
         
         self.Window.lineEdit_z_fail_a.setEnabled(False)
         self.Window.label_z_fail_a.setEnabled(False)
		 
         self.Window.label_z_fail_usb_a.setEnabled(True)
         self.Window.comboBox_z_fail_a.setEnabled(True)
         
         self.Window.Button_z_a.setEnabled(False)
         
		 
         
        
		 
    def updateIpValues(self) :        
       ip_ok = self.Window.lineEdit_z_success.text()
       ip_ko =   self.Window.lineEdit_z_fail.text()
		
       try:
        if IP(str(ip_ok)) :
         MyApp.update_table_ip_ok(self,ip_ok)
         self.Window.label_ip_ok.setStyleSheet("color:green")
         self.Window.label_ip_ok.setText('IP aggiornato')
       except :
         self.Window.label_ip_ok.setStyleSheet("color:red")
         self.Window.label_ip_ok.setText('IP non valido')		
       try : 
        if IP(str(ip_ko)) :
         MyApp.update_table_ip_ko(self,ip_ko)
         self.Window.label_ip_ko.setStyleSheet("color:green")
         self.Window.label_ip_ko.setText('IP aggiornato')
        
       except :
         self.Window.label_ip_ko.setStyleSheet("color:red")
         self.Window.label_ip_ko.setText('IP non valido')
         		 
		 
    def updateIpValues_a(self) :        
        ip_ok = self.Window.lineEdit_z_success_a.text()
        ip_ko =   self.Window.lineEdit_z_fail_a.text()
        
        if IP(str(ip_ok)) :
         MyApp.update_table_ip_ok(self,ip_ok)
         self.Window.label_ip_ok.setStyleSheet("color:green")
         self.Window.label_ip_ok.setText('IP aggiornato')
         
        
        if IP(str(ip_ko)) :
         MyApp.update_table_ip_ko(self,ip_ko)
         self.Window.label_ip_ko.setStyleSheet("color:green")
         self.Window.label_ip_ko.setText('IP aggiornato')
         
        
        				 
   
   
	#controlla la selezione sulla comboBox	RLU o RLUB
    def onChanged(self, text):
      self.rlu_type = text
      return self.rlu_type
	  
    #controlla la selezione sulla comboBox	hw version
    def onChanged_hw(self, text):
      self.hw_version = text
      return self.hw_version
	  
	 #controlla la selezione sulla comboBox	produzione e collaudo 
    def onChanged_pc(self, text):
      self.pc_version = text
      return self.pc_version
	 
    #controlla la selezione sulla comboBox	RLU o RLUB
    def onChanged_again(self, text):
      self.rlu_type = text
      lista_id=[]
      #salvo nella lista gli ID dei device da ricollaudare
      lista_id=self.show_id_for_retry(self.rlu_type) #rlu_type
		#aggiungo questi device alla combobox in modo da poterli selezionare
      self.Window.comboBox_2.clear()
      self.Window.comboBox_2.addItems(lista_id)
	  
      self.serialNumberGPT=self.Window.comboBox_2.currentText()
	  
      query_mnw="SELECT cod_prod FROM RLU where sn_gpt = ?"
      self.id_retry=self.select_generica(self,query_mnw,self.serialNumberGPT)
      self.Window.label_codprod.setText(str(self.id_retry))
	  
      query_nack = "SELECT nack FROM RLU WHERE (ack_2 == '' and nack_2=='' and nack<>'') and sn_gpt = ?" 
      self.nack=self.select_generica(self,query_nack,self.serialNumberGPT)
      self.Window.label_nack.setText(str(self.nack))
	  
      return self.rlu_type	 
	  
	 #controlla la selezione sulla combobox dell'ID del prodotto con NACK del quale rieffettuare il collaudo 
	 #mostra a video nella label il NACK dell'ID selezionato nella combobox
    def onChanged_idForRetry(self, text):
      self.serialNumberGPT = text
	  
      query_nack = "SELECT nack FROM RLU WHERE (ack_2 == '' and nack_2=='' and nack<>'') and sn_gpt = ?" 
      self.nack=self.select_generica(self,query_nack,self.serialNumberGPT)
      self.Window.label_nack.setText(str(self.nack))
	  
      query_mnw="SELECT cod_prod FROM RLU where sn_gpt = ?"
      self.id_retry=self.select_generica(self,query_mnw,self.serialNumberGPT)
      self.Window.label_codprod.setText(str(self.id_retry))
      	  
      return self.serialNumberGPT 
	 
	 #controlla la selezione sulla comboBox cioè numero di device da collaudare
    def valueChange(self):
      
      self.numDevice = self.Window.spinBox.value()
      return self.numDevice
	  
    def onChanged_printer(self, text):
      self.printer_s = text
      
      return self.printer_s
	  
    def onChanged_printer_f(self, text):
      self.printer_f = text
      
      return self.printer_f
	  

	#avvia la finestra principale del circuito di collaudo
    def startMyApp(self):
        self.Window = MyApp(self.rlu_type, self.numDevice, self.id_retry,self.nack, self.hw_version, self.pc_version,self.printer_s,self.printer_f,self.online_printer_success,self.online_printer_fail,self.serialNumberGPT) #item e gli altri fondamentali come gli Intent in android lo passo alla classe
        
        self.setWindowTitle("Facere")
        self.setCentralWidget(self.Window)
        
        #self.Window.pushButton_home.setStyleSheet("border-image: url(C:\\Users\\l.vulpio\\Desktop\\circuito_collaudo\\logo_mail.png)");
        self.Window.pushButton_home.clicked.connect(self.startNewOld) # ok
        #self.getFromComboBox()
        
        self.show()
		







if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    
    app.setWindowIcon(QtGui.QIcon('facere_icon.ico'))
    window = MainWindow()
    window.show()
    
sys.exit(app.exec_())













#if __name__ == "__main__":
#    app = QtGui.QApplication(sys.argv)
#    window = MyApp()
#    window.show()
#sys.exit(app.exec_())


