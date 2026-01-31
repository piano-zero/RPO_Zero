<div align="center">

# 🇮🇹 RPO Zero
### Gestionale Ricevute per Prestazioni Occasionali

![Python](https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python)
![GUI](https://img.shields.io/badge/Interface-Tkinter-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-GPLv3-green?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-v1.1.0_Multi--User-purple?style=for-the-badge)

**Dimentica i fogli Excel e i calcoli a mano.** RPO Zero è lo strumento open-source definitivo per gestire le tue ricevute di prestazione occasionale in Italia, calcolare automaticamente le ritenute e generare PDF pronti per la stampa.

[Caratteristiche](#-caratteristiche-principali) • [Installazione](#-installazione) • [Come Usare](#-come-usare) • [Struttura](#-struttura-del-progetto)

</div>

---

## 🧐 Cos'è RPO Zero?

**RPO Zero** nasce per risolvere un problema comune a molti freelance e lavoratori occasionali in Italia: la complessità del calcolo delle ricevute.

Sei stanco di chiederti:
* *"Devo applicare la marca da bollo?"*
* *"Ho superato la soglia dei 5.000€? Devo pagare l'INPS?"*
* *"Quanto è il netto da ricevere?"*

Questo software fa tutto al posto tuo, tenendo traccia dello storico, gestendo l'anagrafica clienti e avvisandoti quando ti avvicini alle soglie fiscali.

## ✨ Caratteristiche Principali

* 👥 **Multi-Utenza (Novità v1.1):** Supporto per più profili sullo stesso PC. Ogni utente ha i suoi dati, clienti e ricevute separati e protetti da password.
* 🧮 **Calcolo Automatico:** Inserisci il lordo e il software calcola Ritenuta d'Acconto (20%), Gestione Separata INPS (sopra i 5000€), Bollo (2€ sopra i 77,47€) e Netto.
* 📄 **Generatore PDF:** Crea ricevute e Note di Credito professionali in formato PDF (con libreria `fpdf2`), pronte da inviare via email.
* 📊 **Dashboard Intelligente:** Visualizza a colpo d'occhio il fatturato annuo e la distanza dalla soglia "No Tax Area" INPS.
* 🗂 **Anagrafica Completa:** Gestione Clienti (Sostituti d'imposta e Privati) e Gestione Incarichi (CIG, RUP, determine).
* ↩️ **Gestione Storni:** Funzione automatica per generare Note di Credito in caso di errori.
* 💾 **Database Locale:** I tuoi dati restano sul tuo PC (SQLite), nessuna cloud, massima privacy.

## 📸 Screenshots

*(Qui puoi inserire gli screenshot della tua applicazione. Carica le immagini nella cartella del progetto o usa un servizio di hosting e linkale qui)*

| Login Screen | Dashboard | Generazione PDF |
|:---:|:---:|:---:|
| ![Login](https://via.placeholder.com/300x200?text=Screen+Login) | ![Dashboard](https://via.placeholder.com/300x200?text=Screen+Dashboard) | ![PDF](https://via.placeholder.com/300x200?text=Esempio+PDF) |

## 🚀 Installazione

### Prerequisiti
* Python 3.8 o superiore installato sul sistema.

### Passaggi

1.  **Clona il repository** (o scarica lo zip):
    ```bash
    git clone [https://github.com/TUO_USERNAME/RPO-Zero.git](https://github.com/TUO_USERNAME/RPO-Zero.git)
    cd RPO-Zero
    ```

2.  **Installa le dipendenze:**
    Il software utilizza `fpdf2` per la generazione dei PDF.
    ```bash
    pip install fpdf2
    ```
    *(Tkinter è solitamente incluso nell'installazione standard di Python)*

3.  **Avvia l'applicazione:**
    ```bash
    python main.py
    ```

## 🛠 Struttura del Progetto

Il progetto è modulare e facile da mantenere:

* `main.py` 🧠: Il cuore dell'applicazione. Gestisce l'interfaccia grafica (GUI), la logica di login e il flusso operativo.
* `gestore_db.py` 🗄: Gestisce tutte le operazioni sul database SQLite (creazione tabelle, query, multi-utenza).
* `pdf_generator.py` 📄: Modulo dedicato alla creazione estetica e funzionale dei file PDF.
* `ricevute_pdf/` 📂: Cartella creata automaticamente dove vengono salvati i file generati.
* `gestionale_ricevute.db` 💾: Il file database (creato automaticamente al primo avvio).

## 📖 Come Usare

1.  **Registrazione:** Al primo avvio, clicca su "Registra Nuovo Utente" per creare il tuo profilo (Username e Password).
2.  **Setup Profilo:** Una volta loggato, compila i tuoi dati fiscali (Nome, CF, Indirizzo, IBAN) nella sezione "Mio Profilo".
3.  **Parametri:** Verifica in "Parametri Fiscali" che le soglie siano aggiornate per l'anno corrente (il software prova a impostarle in automatico).
4.  **Workflow:**
    * Crea un **Cliente**.
    * Crea un **Incarico** associato a quel cliente.
    * Vai su **Nuova Ricevuta**, seleziona l'incarico, inserisci l'importo e salva!

## 🤝 Contribuire

I contributi sono benvenuti! Se hai idee per migliorare il codice o vuoi aggiungere nuove funzionalità:

1.  Fai un **Fork** del progetto.
2.  Crea un branch per la tua feature (`git checkout -b feature/NuovaFeature`).
3.  Fai **Commit** delle modifiche (`git commit -m 'Aggiunta NuovaFeature'`).
4.  Fai **Push** sul branch (`git push origin feature/NuovaFeature`).
5.  Apri una **Pull Request**.

## 📄 Licenza

Distribuito sotto licenza **GNU General Public License v3.0**. Vedi `LICENSE` per maggiori informazioni.

---

<div align="center">
  
  Created with ❤️ by [Rodolfo Sabelli](https://github.com/TUO_USERNAME)
  
  *Se questo progetto ti è stato utile, lascia una ⭐️ al repository!*

</div>
