# -*- coding: utf-8 -*-

import sys
import os
import crcmod
import sqlite3
import serial
import time
#import subprocess
#from threading import Thread
#from multiprocessing import Pool
#from multiprocessing.dummy import Pool as ThreadPool
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtGui import QFileDialog, QApplication, QMainWindow, QPushButton, QWidget
import pyodbc # PER CONNETTERSI AD AZURE
qtCreatorFile = "circuito_collaudo_RLU.ui" # layout main window.

qtCreatorFile_new_old = "new_old.ui" #layout prima finestra per scegliere se collaudare un nuovo device o uno vecchio
qtCreatorFile_rlu_rluB = "rlu_rlub.ui" #layout seconda finestra per scegliere la tipologia di dispositivo
qtCreatorFile_rlu_rluB_again = "rlu_rlub_again.ui" #layout seconda finestra per scegliere la tipologia di dispositivo 

oracolo = False
oracoloBin = ''
path = ''


ser = serial.Serial()
#ser.port = "COM18"


ser.baudrate = 115200
ser.bytesize = serial.EIGHTBITS #number of bits per bytes
ser.parity = serial.PARITY_NONE #set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE #number of stop bits



ser.timeout = 0             #non-block read
ser.xonxoff = False     #disable software flow control
ser.rtscts = False     #disable hardware (RTS/CTS) flow control
ser.dsrdtr = False       #disable hardware (DSR/DTR) flow control
ser.writeTimeout = 2     #timeout for write

tentativi = 0

Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)
Ui_new_old, QtBaseClass = uic.loadUiType(qtCreatorFile_new_old)
Ui_rlu_rlub, QtBaseClass = uic.loadUiType(qtCreatorFile_rlu_rluB)
Ui_rlu_rlub_again, QtBaseClass = uic.loadUiType(qtCreatorFile_rlu_rluB_again)


RED_STYLE = """

QProgressBar::chunk {
    background-color: red;
	
}
"""




class MyApp(QtGui.QMainWindow, Ui_MainWindow):


    #costruttore, qui referenzio i widget e gestisco il flusso di lavoro mediante gli eventi
    def __init__(self, item, numDevice, serial):
        #elemento che recupero dall'altra classe e lo passo anche qui sopra alla funzione init
        print "combo_box_main  item :  "+str(item)
        print "num device :  "+str(numDevice)
        print "seriale :" +str(serial)		
		
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.setFixedSize(1300, 1000)
        #selezione file binario
        self.selectFile_toolButton.clicked.connect(self.select_file)
        #pulsante ok
        self.buttonBox.accepted.connect(self.right_file)      
        #DEBUG uso il pulsante canc per test e prove varie - la sua funzione e -wrong_file()-
        #self.buttonBox.rejected.connect(self.wrong_file)
        self.buttonBox.rejected.connect(self.select_num_coll)

        #self.serialGenerator(numDevice)
        #pulsante avvia collaudo
        #self.avviaCollaudotoolButton.clicked.connect(lambda:self.check_data(oracolo))
		
		  #se è stato selezionato RLU il collaudo è completo, altrimenti con RLU_B non testo irda2 e misura corrente
        
           
        self.avviaCollaudotoolButton.clicked.connect(lambda:self.serialGenerator(numDevice, tentativi, item))
       
          
        #da implementare e gestire lo stop del collaudo
        #self.fermaCollaudotoolButton.clicked.connect(?)


        #PULSANTI DEBUG
        #queste funzioni andranno poi triggerate da check_data
        self.btn_abilitaPrg.clicked.connect(lambda:self.abilita_programmazione(tentativi))
        self.btn_disabilitaPrg.clicked.connect(lambda:self.disabilita_programmazione(tentativi))
        self.btn_IRDA2.clicked.connect(lambda:self.test_irda2(tentativi))
        self.btn_getKey.clicked.connect(lambda:self.get_key(tentativi))
        self.btn_testTrans.clicked.connect(lambda:self.test_transceiver(tentativi))
        self.btn_ricarica.clicked.connect(lambda:self.misura_corrente_ricarica(tentativi))
        self.btn_echo.clicked.connect(lambda:self.echo())
        #/PULSANTI DEBUG


        #pulsante "ProgrammaFW"
        self.btn_shellCmd.clicked.connect(self.shell_commands)

        self.buttonBox_2.accepted.connect(lambda:self.reTest(oracolo))
        self.buttonBox_2.rejected.connect(self.cancelPressed)
		
    
	
    #genera seriali del tipo "0A..999A..0B..999B"	manca la aprte B,C,d etc devo salvare eleggere i dati dal DB
	 #a collaudo finito abilito un flag che prosegue a collaudare il successivo.
    def serialGenerator(self, numDevice, tentativi, item) :
   #salvare nel DB l'ultimo seriale cosichhè poi posso ripartire da lì per le volte successive
        startNumber = 000
        startLetter = 'A'

        for x in range(numDevice):
         startNumber+=1
         serial = str(startNumber)+startLetter
		   if item == 'RLU' :
          self.avviaCollaudoRLU(tentativi, serial)
         else :
		    self.avviaCollaudoRLU_B(tentativi, serial)
        # qui insert into DB ultimo seriale
    

     	
		
    def avviaCollaudoRLU(self, tentativi, serial):

	     # passare serial a tutte le funzioni sotto che a seconda del risultato lo scriveranno nel DB assieme all'esito #del collaudo nel dettaglio. i Fail andranno in una tabella apposita da cui recuperare gli ID e farli selezionare
        # all'utente anzichè come ora inseire a mano	per i retry.

        #nel DB leggere l'ultimo seriale collaudato che sarà poi base di partenza per l'incremento		
        print "new_serial :"+serial
        self.abilita_programmazione(tentativi)
        time.sleep(2)
        self.disabilita_programmazione(tentativi)
        time.sleep(2)
        self.test_irda2(tentativi)
        time.sleep(2)
        self.get_key(tentativi)
        time.sleep(2)
        self.test_transceiver(tentativi)
        time.sleep(2)
        self.misura_corrente_ricarica(tentativi)
        print "DONE"
		
    def avviaCollaudoRLU_B(self, tentativi):
        print "new_serial :"+serial
        self.abilita_programmazione(tentativi)
        time.sleep(2)
        self.disabilita_programmazione(tentativi)
        time.sleep(2)
        #self.test_irda2(tentativi)
        #time.sleep(2)
        self.get_key(tentativi)
        time.sleep(2)
        self.test_transceiver(tentativi)
        #time.sleep(2)
        #self.misura_corrente_ricarica(tentativi)
        print "DONE"
        

    def cancelPressed(self):
        self.buttonBox_2.setEnabled(False)
        checkLabel = self.check_label.setText('')



    def reTest(self,oracolo):
        #invece della delete deve fare un'update con il numero dei collaudi e/o gli esiti
        self.delete_from_db()
        self.check_data(oracolo)




    #controllo correttezza dati, gestisco  warning label
    def check_data(self,oracolo):

            serialNumber = self.getSN()
            barCode = self.getBarCode()
            prodCode = self.getProdCode()
            code = str(prodCode)
            #quando il formato sara definito faro gli opportuni controlli tipo lunghezza o byte etc
            if (barCode and prodCode and serialNumber) == '' :
                self.check_label.setStyleSheet('color: red')
                checkLabel = self.check_label.setText('Dati mancanti o errati')
            else:
                self.check_label.setStyleSheet('color: green')
                checkLabel = self.check_label.setText('Dati corretti')
                oracoloBin = self.rightFile_label.text()
                if oracoloBin == 'File caricato con successo' :
                    #creo il DB, se non esiste
                    self.create_db()
                    #eseguo una select per controllare i dati nel db e se non ci sono ack per quel prodCode, imposto oracolo a true, consentendo la insert
                    oracolo = self.select_from_db(prodCode,serialNumber,oracolo)
                    #DEBUG
                    print "in check data prima dell'if : "+str(oracolo)
                    if oracolo == True :
                        numCol = self.select_num_coll()
                        self.insert_into_db(serialNumber,barCode,prodCode,"","","",numCol) #'1'HARDCODED SOSTITUIRE CON UNA SELECT/GET FROM CAMPO TESTO
                        #di fianco alla scritta "Matricola in Collaudo" indico il seriale ? TBD
                        self.matCol_label.setText(serialNumber)



    #genero il ST con crc16
    def system_title_generator(self):
        serialNumber = str(self.serialNumber_text.text())
        serialNumberReverse = serialNumber[::-1]
        crc16 = crcmod.predefined.Crc('crc-16-dnp')
        crc16_R = crcmod.predefined.Crc('crc-16-dnp')
        crc16_R.update(serialNumberReverse)
        crc16.update(serialNumber)
        snCrc16 = crc16.hexdigest()
        snCrc16_R = crc16_R.hexdigest()
        #inverto i bytes perche emiliano ha usato un dnp leggermente diverso
        snCrc16TwoLastBytes  = snCrc16[-2:]
        snCrc16TwoFirstBytes = snCrc16[:2]

        snCrc16TwoLastBytes_R  = snCrc16_R[-2:]
        snCrc16TwoFirstBytes_R = snCrc16_R[:2]

        system_title = 'D735'+snCrc16TwoLastBytes+snCrc16TwoFirstBytes+snCrc16TwoLastBytes_R+snCrc16TwoFirstBytes_R+'0102'

        return system_title

    #DEBUG funzione che nasce per stampare l'ST ma la uso per debug vari
    def print_st(self):
        #st = self.system_title_generator()
        print st
        #self.progressBar.setValue(14.28571428571429)

        #self.update_table()


    #selezione file binario
    def select_file(self):
        self.rightFile_label.setText('')
        self.lineEdit.setText(QFileDialog.getOpenFileName())

    #click 'OK'
    def right_file(self):
        path = self.lineEdit.text()
        if path != '' and path[-3:]== 'bin':
            self.rightFile_label.setStyleSheet('color: green')
            self.rightFile_label.setText('File caricato con successo')
            oracoloBin = True
        else :
            path=''
            self.rightFile_label.setStyleSheet('color: red')
            self.rightFile_label.setText('Formato del file non corretto')
            oracoloBin = False
            #debug
        return oracoloBin

    #click 'Cancel'
    def wrong_file(self):
        path = ''
        self.rightFile_label.setText(path)
        self.lineEdit.setText(path)
        #debug
        print path


    def getSN(self):
      serialNumber = self.serialNumber_text.text()
      return serialNumber

    def getBarCode(self):
      barCode = self.barCode_text.text()
      return barCode

    def getProdCode(self):
      prodCode = self.prodCode_text.text()
      return prodCode


    #func per creare il DB
    def create_db(self):
        conn = sqlite3.connect('Database\\rluDB.db')
        conn.execute('CREATE TABLE IF NOT EXISTS RLU (cod_prod TEXT PRIMARY KEY, seriale TEXT, barcode TEXT, getkey TEXT, ack TEXT, nack TEXT,num_collaudi TEXT)')
        conn.close()

    #func per inserire nel DB
    def insert_into_db(self,serialNumber,barCode,prodCode,getKey,ACK,NACK,numCollaudi):
        try:
         self.delete_from_db()
        except Exception,e : print "prodCode non presente nel db or "+str(e)
        time.sleep(2)
        list = [str(prodCode),str(serialNumber),str(barCode),str(getKey),str(ACK),str(NACK),str(numCollaudi)]
        conn = sqlite3.connect('Database\\rluDB.db')
        with conn :
         cursor = conn.cursor()
         cursor.executemany('INSERT INTO RLU values (?,?,?,?,?,?,?)',[list])

    #func per aggiornare il DB
    def update_table(self):
        #DOVRANNO DIVENTARE GLOBALI E PASSATE COME ARGOMENTO SOPRATTUTTO QUANDO CI SARANNO GLI ACK
        prodCode = self.getProdCode()
        code = str(prodCode)
        error = 'errore_generico'

        conn = sqlite3.connect('Database\\rluDB.db')
        with conn :
            cursor = conn.cursor()
            #cursor.execute("""UPDATE RLU SET cod_prod = ? , seriale = ?, barcode = ?, getkey = ?, ack = ?, nack = ? WHERE cod_prod = ? """,('xxx','yyy','kkk','zzz','jjj','prova','7777777777'))
            cursor.execute("""UPDATE RLU SET  nack = ? WHERE cod_prod = ? """,(error,code))
        #TODO
        #faccio la select su num_collaudi  al numero ottenuto sommo 1
        #RICHIAMARE LA FUNZIONE CHE FA LA SELECT DAL DB DEL NUMCOLL

            #cursor.execute("""UPDATE RLU SET  num_collaudi = ? WHERE cod_prod = ? """,(num_to_update,code))


    def delete_from_db(self):
        self.buttonBox_2.setEnabled(False)
        prodCode = self.getProdCode()
        code = str(prodCode)
        conn = sqlite3.connect('Database\\rluDB.db')
        with conn :
         cursor = conn.cursor()
         cursor.execute("""DELETE FROM RLU WHERE cod_prod = ? """,(code,))


    def select_from_db(self,prodCode,serialNumber,oracolo):

        """
        Controllo  i dati sul db con una select, se gia presente un ack(segno che il device e stato collaudato con successo) compare msg di errore
        altrimenti oracolo consente la insert del BarCode,Codice Produzione,Serial Number
        @param prodCode : codice inserito dall'utente nella form
        @param serialNumber : codice inserito dall'utente nella form
        @return Oracolo : valore booleano che verrà passato ad una funzione che gestisce la insert abilitandola o disabilitandola

        """
        #oracolo = False
        #DEBUG
        print "all'inizio di select_from_db : "+str(oracolo)
        conn = sqlite3.connect('Database\\rluDB.db')
        #cast a string altrimenti in questo caso non gli piace
        code = str(prodCode)
        with conn :
         cursor = conn.cursor()
         cursor.execute('SELECT ack FROM RLU WHERE cod_prod = ?',(code,))
         data = cursor.fetchall()
         dati = str(data)
         print dati
         if (dati != "[(u'',)]" and dati !='[]') :
            for item in dati :
                for word in item :
                    if (word != "") :
                        self.check_label.setStyleSheet('color: red')
                        checkLabel = self.check_label.setText('Il device risulta collaudato.Procedere ugualmente? ')
                        self.buttonBox_2.setEnabled(True)
                        self.select_num_coll()

         else :
             oracolo = True
         #debug
         print "alla fine di select_from_db"+ str(oracolo)
         return oracolo


    def select_num_coll(self):
        conn = sqlite3.connect('Database\\rluDB.db')
        prodCode = self.getProdCode()
        code = str(prodCode)
        num = 0
        with conn :

         cursor = conn.cursor()
         cursor.execute('SELECT num_collaudi FROM RLU WHERE cod_prod = ?',(code,))
         data = cursor.fetchall()
         for item in data :
             for word in item :
                 try :
                     numero=int(word)
                     num = str(numero)
                     print 'numero : '+num
                 except Exception, e:
                     print "non e un numero: " + str(e)
        self.lcdNumber.display(num)
        return num




# ################################################################################OPERAZIONI SULLA SERIALE###############################################################################

# NOTA - per il me stesso del futuro o chiunque altro : si, potevo scrivere una funzione sola e passargli gli opportuni parametri, ma il tempo e poco ed il copincolla è un arte
# inoltre per il debug e piu comodo dato che sono eventi triggerati da dei pulsanti.

    def ack_nack(self,risposta,label,barra):
	    
        #ACK
		
        if risposta[:1] == "\x15":
            
            barra.setStyleSheet(RED_STYLE)
            label.setStyleSheet('color: red')
        
		  #NACK

        if risposta == "\x06\x00\x00":
             label.setText("prog disabilitata")
             self.progressBar.setValue(28.57142857142857)
			 
        #150100[comando non valido]
        elif risposta == "\x15\x01\x00":
             label.setText("comando non valido")
              
		  #150200[err corrente]
        elif risposta == "\x15\x02\x00":
             label.setText("err misura corrente")
             
		  #150301[irda_1 ko] 
        elif risposta == "\x15\x03\x01":
             label.setText("test IRDA_1 ko")
               
		  #150302[irda_2 ko]	 
        elif risposta == "\x15\x03\x02":
             label.setText("test IRDA_2 ko")
             
             
		  #150303[irda_1 & irda_2 ko] 
        elif risposta == "\x15\x03\x03":
             label.setText("test IRDA_1,IRDA_2 ko")
             
		  #150400[test transceiver err] 	 
        elif risposta == "\x15\x04\x00":
             label.setText("test transceiver non riuscito")
            
		  #150500[test EEPROM err] 
        elif risposta == "\x15\x05\x00":
             label.setText("test EEPROM non riuscito")
             
		  #150600[Test Key err]
        elif risposta == "\x15\x06\x00":
             label.setText("test KEY non riuscito")
               
        #150700[corrente out of range]			 
        elif risposta == "\x15\x07\x00":
             label.setText("corrente out of range")
            
		  #150800[rssi out of range]
        elif risposta == "\x15\x08\x00":
             label.setText("rssi out of range")
                
		  #151500[generico]
        else :
            label.setText("errore generico, comunicazione interrotta ")
           
            


    #in risposta mi aspetto HW/FIRMWARE_VERSION 
    # impostare condizione che se RLU-B 550200 altrimenti 550100
    def abilita_programmazione(self, tentativi):  
        barra = self.progressBar_2
        barra.reset()
        secondi = 60.0000000000
        label = self.labelBar_1
        text = "programmazione on"
        command_ = "550200" #0x550200 per RLU-B  550100 per RLU
        command = command_.decode("hex")
        risposta = self.write_read_serial(command,secondi,barra,label,text)
        risposta_ex = risposta.encode("hex")
		
        hw_version = str(int(risposta_ex[2:-2], 16)) #hw version base 10
        fw_version = str(int(risposta_ex[-2:], 16)) #sw version base_10
        command_r = risposta_ex[:2] #comando 50
       
       # print ('hw : ' + hw_version)
       # print ('sw : ' + fw_version)
       # print ('cmd : ' + command_r)
		
        tentativi+=1

        if command_r == "50" :
           label.setText("programmazione ok")
           barra.setValue(secondi)
           self.progressBar.setValue(20)
        else :
           if tentativi==1 :
              
              print "retry"
              self.abilita_programmazione(tentativi)
           else :
              self.ack_nack(risposta,label,barra)
              barra.setValue(secondi)#100%
             
           

    #in risposta ACK/NACK : 
    def disabilita_programmazione(self, tentativi):
        barra = self.progressBar_3
        secondi = 20.0000000000
        label = self.labelBar_2
        text = "programmazione off"
        prodCode = self.getProdCode()
        command_ = "560000"
        command = command_.decode("hex")
        risposta = self.write_read_serial(command,secondi,barra,label,text)
        tentativi+=1
        if risposta == "\x06\x00\x00":
            self.ack_nack(risposta,label,barra)
            barra.setValue(secondi)
            self.progressBar.setValue(40)
        else :
           if tentativi==1 :
              
              print "retry"
              self.disabilita_programmazione(tentativi)
           else :
              self.ack_nack(risposta,label,barra)
              barra.setValue(secondi)
              

    def test_irda2(self, tentativi):
        barra = self.progressBar_4
        secondi = 50.0000000000
        label = self.labelBar_3
        text = "test irda2"
        command_ = "570000"
        command = command_.decode("hex")
        risposta = self.write_read_serial(command,secondi,barra,label,text)
        tentativi+=1
        if risposta == "\x06\x00\x00":
            self.ack_nack(risposta,label,barra)
            barra.setValue(secondi)
            self.progressBar.setValue(60)
        else :
           if tentativi==1 :
              
              print "retry"
              self.test_irda2(tentativi)
           else :
              self.ack_nack(risposta,label,barra)
              barra.setValue(secondi)
		

		
    def get_key(self, tentativi):
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
        print ('cmd : ' + command_r)
     		
        tentativi+=1
        if command_r == "59": 
            label.setText("key ok")
            barra.setValue(secondi)
            print ('key : ' + key)
            self.progressBar.setValue(80)
        else :
           if tentativi==1 :
              
              print "retry"
              self.get_key(tentativi)
           else :
              self.ack_nack(risposta,label,barra)
              barra.setValue(secondi)
			
		#torna il seriale che devo salvare nel DB (manca questa parte) e l'RSSI che se < 240 considero NACK
    def test_transceiver(self, tentativi):
        barra = self.progressBar_6
        secondi = 30.0000000000
        label = self.labelBar_5
        text = "test transceiver"
        command_ = "580000"
        command = command_.decode("hex")
    	
        risposta = self.write_read_serial(command,secondi,barra,label,text) #ascii
        #la funz ser.readline() torna un ASCII che riconverto in hex
        risposta_ex = risposta.encode("hex") #58d735bb7617100133c 
        seriale = risposta_ex[2:-2]#seriale es d735bb761710013
        rssi = risposta_ex[-2:] #RSSI es c3
        rssi_10 = int(rssi, 16) #RSSI base 10
        tentativi+=1
        if risposta != "\x15\x04\x00":
            if(rssi_10 >= 240) :
              label.setText("trans ok")
              barra.setValue(secondi)
              self.progressBar.setValue(100)
            else :
              if tentativi==1 :
               print "retry"
               self.test_transceiver(tentativi)
              else :
               self.ack_nack("\x15\x08\x00",label,barra)
               barra.setValue(secondi)
        else :
            if tentativi==1 :
              
              print "retry"
              self.test_transceiver(tentativi)
            else :
              self.ack_nack(risposta,label,barra)
              barra.setValue(secondi)
			
   #torna la corrente che se < 32 considero come NACK
    def misura_corrente_ricarica(self, tentativi):
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
              label.setText("corrente ok")
              barra.setValue(secondi)
              self.progressBar.setValue(20)
           else :
              if tentativi==1 :
               print "retry"
               self.misura_corrente_ricarica(tentativi)
              else :
               self.ack_nack("\x15\x07\x00",label,barra)
               barra.setValue(secondi)  
             
        else :
           if tentativi==1 :
              print "retry"
              self.misura_corrente_ricarica(tentativi)
           else :
              self.ack_nack(risposta,label,barra)
              barra.setValue(secondi)

    def echo(self):
        barra = self.progressBar_8
        secondi = 30.0000000000
        label = self.labelBar_7
        barra.setValue(0)
        text = "test corrente"

        command_ = "0F0000" #0x13 o 0x16 etc
        command = command_.decode("hex")
        risposta = self.write_read_serial(command,secondi,barra,label,text)
        if risposta == command :
            label.setText( "echo ok")
            barra.setValue(secondi)
        elif risposta != command :
            label.setStyleSheet("color:red")
            label.setText( "error echo")
        else :
            label.setStyleSheet("color:red")
            label.setText("errore generico, comunicazione interrotta ")



    

	# Cicla per 'n' secondi, quando riceve una risposta la salva nella variabile per il return.
	#termina in ogni caso il ciclo di 'n' secondi così da non interrompere le animazioni della barra.
	
    def write_read_serial(self,command,secondi,barra,label,text) :
            #fondamentale per evitare il freeze della GUI
            gui=QtGui.QApplication.processEvents
			   #prendo il numero di COM dall input text
            com_port_number = self.COM_edit.text()
            ser.port = "COM"+str(com_port_number)
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
							print("write data : " + command,)
							startTime = time.time()                    
							#label.setText("ATTENDERE "+ str(secondi)[:2] +" SECONDI PER LA RISPOSTA...")
							label.setText(text)
							while time.time()-startTime <= secondi :
								#fondamentale per evitare il freeze della GUI
								gui()
								response = ser.readline()
								barra.setValue(time.time()-startTime)
								#print ("resp : "+response,)

								if (response!=''):
								 
								 resp += response
								 print ("resp : "+resp,)
								 
								 time.sleep(3)
								 break
								 
								
							ser.close()
							if(response=='') :
							 label.setText("cdc non risponde: riprova ")
							 label.setStyleSheet("color:yellow")
                       		
					   
						except Exception, e1:
							print "error communicating...: " + str(e1)

					else:
						print "cannot open serial port "
            return resp





# ################################################################################ PROCEDURA PROGRAMMAZIONE FIRMWARE ###############################################################################

    #comandi che vengono lanciati in sequenza nella shell
    def shell_commands(self) :
        #subprocess.call(['','',''])

        os.system('cd C:\Program Files (x86)\STMicroelectronics\STM32 ST-LINK Utility\ST-LINK Utility')
        #os.system('dir')
        os.system('ST-LINK_CLI.exe –c ID=0 SWD FREQ=0 UR')
        os.system('ST-LINK_CLI.exe -ME')
        os.system('ST-LINK_CLI.exe –P'+path+'0x08000000 –V after_programming')  #path bootloader
        os.system('ST-LINK_CLI.exe –P'+path2+'0x0800c800 –V after_programming') #path fw
        os.system('ST-LINK_CLI.exe –Rst')





############################################################################################################################
###########################################INSERIMENTO ID E CHIAVE NEL DB AZURE#############################################
############################################################################################################################

# O TRIGGERATA DA UN PULSANTE O AUTOMATIZZATA CIOè DOPO COLLAUDO, IN CASO DI SUCCESSO, SALVA QUESTE INFO SUL DB AZURE
# ANDRANNO PASSATI I VALORI OPPORTUNI PRESI DAL CAMPO DI TESTO O SIMILI



#def return_bytes(the_bytes):
#    return the_bytes
    
#server = 'citymonitoreu.database.windows.net'
#database = 'citymonitor'
#username = 'citymonitor_dbadmin@citymonitoreu'
#password = 'MonitCityMenoWatt1296'
#driver= '{ODBC Driver 17 for SQL Server}'
#conn = pyodbc.connect('DRIVER='+driver+';SERVER='+server+';PORT=1433;DATABASE='+database+';UID='+username+';PWD='+ password)

					  				  

#cursor = conn.cursor()

#conn.add_output_converter(-155, return_bytes) #!FONDAMENTALE! ALTRIMENTI ERRORE
	
#cursor.execute('''
#                INSERT INTO [Todoitem] (ID, text)
#                VALUES
#                ('D7351C973A6A0102 ', '608b44f3c7cea699423d170815bfeca4')
#                ''')

				
#conn.commit()				
#cursor.close()
#conn.close()







   
   


class RluRluB(QtGui.QMainWindow,Ui_rlu_rlub):
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
        self.setWindowTitle("New_Old")
        self.setCentralWidget(self.NewOld)
        
        self.NewOld.NewButton.clicked.connect(self.startRluRluB) # clicco e avvia la finestra di scelta
        #TODO : cambiare comportamento cioè far inserire in ID o proporlo a video tra quelli FAIL
        self.NewOld.OldButton.clicked.connect(self.startRluRluB_again) # clicco e avvia la finestra di scelta
        self.show()


    #avvia la finestra rlu-rlub
    def startRluRluB(self):
        self.Window = RluRluB()
        self.setWindowTitle("RluRluB")
        self.setCentralWidget(self.Window)
		
        
		
		  #al click del pulsante "ok" avviao la main win chiamata Myapp
        self.Window.pushButton.clicked.connect(self.startMyApp) # ok
        
        #lista 
        list1 = [('RLU'),('RLU_B'),]
		  #pulisco poi popolo la lista
        self.Window.comboBox.clear()
        self.Window.comboBox.addItems(list1)
       
        
        #al cambio elemento nella combobox assegna il valore alla variabile
        self.item=self.Window.comboBox.activated[str].connect(self.onChanged)
        #assegna il valore statico alla variabile, cioè se non cambio e lascio quello di default 
        self.item=self.Window.comboBox.currentText()
        #al cambio elemento nella spinbox assegna il valore alla variabile
        self.numDevice=self.Window.spinBox.valueChanged[str].connect(self.valueChange)
        #altrimenti crasha
        self.serial = None
        
        self.show()
		
	#avvia la finestra rlu-rlub
	
    def startRluRluB_again(self):
        self.Window = RluRluB_again()
        self.setWindowTitle("RluRluB")
        self.setCentralWidget(self.Window)
		
        
		
		  #al click del pulsante "ok" avviao la main win chiamata Myapp
        self.Window.pushButton.clicked.connect(self.startMyApp) # ok
        
        #lista 
        list1 = [('RLU'),('RLU_B'),]
		  #pulisco poi popolo la lista
        self.Window.comboBox.clear()
        self.Window.comboBox.addItems(list1)
       
        
        #al cambio elemento nella combobox assegna il valore alla variabile
        self.item=self.Window.comboBox.activated[str].connect(self.onChanged)
        #assegna il valore statico alla variabile, cioè se non cambio e lascio quello di default 
        self.item=self.Window.comboBox.currentText()
        #prelevo il seriale da collaudare di nuovo
        self.serial=self.Window.textEdit.textChanged.connect(self.valueC)
		  #altrimenti crasha
        self.numDevice = 0
        
        self.show()
		
   
	#controlla la selezione sulla comboBox	RLU o RLUB
    def onChanged(self, text):
      self.item = text
      return self.item
	 
	 #controlla la selezione sulla comboBox cioè numero di device da collaudare
    def valueChange(self):
      
      self.numDevice = self.Window.spinBox.value()
      return self.numDevice
	  
    #controlla l'inserimento sulla textEdit DOVREBBE FARE QUERY TRA I FAIL E PROPORRE A VIDEO UNA LISTA
    def valueC(self):
      
      self.serial = self.Window.textEdit.toPlainText()
      return self.serial    
        
		
		
	#avvia la finestra principale del circuito di collaudo
    def startMyApp(self):
        self.Window = MyApp(self.item, self.numDevice, self.serial) #item e gli altri fondamentali come gli Intent in android lo passo alla classe
        
        self.setWindowTitle("MyApp")
        self.setCentralWidget(self.Window)
		
        #self.getFromComboBox()
        
        self.show()
		







if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    window.show()
sys.exit(app.exec_())












#if __name__ == "__main__":
#    app = QtGui.QApplication(sys.argv)
#    window = MyApp()
#    window.show()
#sys.exit(app.exec_())


