# RPO Zero - Gestionale Ricevute Prestazione Occasionale
# Versione Monolitica 2.0.0 (Multi-Utente)
# Tutti i moduli integrati in un unico file

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
import sqlite3
import hashlib
import platform
import subprocess
from fpdf import FPDF
from fpdf.enums import XPos, YPos  # <--- Aggiungi questa riga
import os

# =========================================================================
# MODULO 1: DATABASE HANDLER
# =========================================================================

DB_NAME = "rpo_zero.db"

class DatabaseHandler:
    def __init__(self):
        self.db_name = DB_NAME
        self.init_db()  # Inizializza le tabelle al primo avvio

    def _get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        # Abilita vincoli foreign keys
        conn.execute("PRAGMA foreign_keys = ON") 
        return conn

    def init_db(self):
        """Crea la struttura del database se non esiste (Multi-utente)."""
        conn = self._get_connection()
        cur = conn.cursor()
        
        # 1. Tabella Utenti (Login)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT
        )
        """)

        # 2. Profilo Professionale (Dati Fiscali dell'utente)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            nome_completo TEXT,
            codice_fiscale TEXT,
            indirizzo TEXT,
            iban TEXT,
            email TEXT,
            telefono TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # 3. Configurazione Fiscale
        cur.execute("""
        CREATE TABLE IF NOT EXISTS fiscal_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            anno INTEGER NOT NULL,
            soglia_inps_no_tax REAL,
            aliquota_gestione_separata REAL,
            quota_carico_utente REAL,
            soglia_bollo REAL,
            valore_bollo REAL,
            UNIQUE(user_id, anno),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # 4. Clienti
        cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ragione_sociale TEXT NOT NULL,
            piva_cf TEXT NOT NULL,
            indirizzo TEXT,
            email_amministrazione TEXT,
            sostituto_imposta BOOLEAN DEFAULT 0,
            note TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # 5. Incarichi
        cur.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            descrizione_progetto TEXT,
            data_inizio TEXT,
            rif_determina_incarico TEXT,
            data_determina TEXT,
            nome_rup TEXT,
            email_rup TEXT,
            cig TEXT,
            stato TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
        """)

        # 6. Ricevute
        cur.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            assignment_id INTEGER NOT NULL,
            numero_progressivo INTEGER,
            anno_riferimento INTEGER,
            data_emissione TEXT,
            descrizione_prestazione TEXT,
            importo_lordo REAL,
            imponibile_inps REAL,
            aliquota_inps_applicata REAL,
            ritenuta_inps_totale REAL,
            quota_inps_utente REAL,
            aliquota_ritenuta_acconto REAL,
            importo_ritenuta_acconto REAL,
            rimborso_spese_esenti REAL,
            bollo_applicato BOOLEAN,
            importo_bollo REAL,
            netto_a_pagare REAL,
            file_path_pdf TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(assignment_id) REFERENCES assignments(id)
        )
        """)
        
        conn.commit()
        conn.close()

    # --- AUTENTICAZIONE ---
    def register_user(self, username, password, display_name):
        conn = self._get_connection()
        cur = conn.cursor()
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        try:
            cur.execute("INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)", 
                        (username, pwd_hash, display_name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False # Username già in uso
        finally:
            conn.close()

    def login_user(self, username, password):
        conn = self._get_connection()
        cur = conn.cursor()
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        cur.execute("SELECT id, display_name FROM users WHERE username=? AND password_hash=?", (username, pwd_hash))
        result = cur.fetchone()
        conn.close()
        return result # Ritorna tuple (id, display_name) o None

    # --- GESTIONE PROFILO UTENTE ---
    def get_user_profile(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_profile WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def save_user_profile(self, user_id, nome, cf, indirizzo, iban, email, telefono):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM user_profile WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            query = """UPDATE user_profile SET 
                       nome_completo=?, codice_fiscale=?, indirizzo=?, iban=?, email=?, telefono=? 
                       WHERE user_id=?"""
            cursor.execute(query, (nome, cf, indirizzo, iban, email, telefono, user_id))
        else:
            query = """INSERT INTO user_profile 
                       (user_id, nome_completo, codice_fiscale, indirizzo, iban, email, telefono) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)"""
            cursor.execute(query, (user_id, nome, cf, indirizzo, iban, email, telefono))
        conn.commit()
        conn.close()

    # --- CONFIGURAZIONE FISCALE ---
    def ensure_fiscal_config_exists(self, user_id, anno):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT anno FROM fiscal_config WHERE user_id = ? AND anno = ?", (user_id, anno))
        exists = cursor.fetchone()
        
        if not exists:
            query = """
                INSERT INTO fiscal_config 
                (user_id, anno, soglia_inps_no_tax, aliquota_gestione_separata, quota_carico_utente, soglia_bollo, valore_bollo)
                VALUES (?, ?, 5000.00, 24.00, 0.33333333, 77.47, 2.00)
            """
            cursor.execute(query, (user_id, anno))
        conn.commit()
        conn.close()

    def get_fiscal_config(self, user_id, anno):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fiscal_config WHERE user_id = ? AND anno = ?", (user_id, anno))
        result = cursor.fetchone()
        conn.close()
        return result

    def save_fiscal_config(self, user_id, anno, soglia, aliquota, quota, s_bollo, v_bollo):
        conn = self._get_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO fiscal_config 
            (user_id, anno, soglia_inps_no_tax, aliquota_gestione_separata, quota_carico_utente, soglia_bollo, valore_bollo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, anno) DO UPDATE SET
            soglia_inps_no_tax=excluded.soglia_inps_no_tax,
            aliquota_gestione_separata=excluded.aliquota_gestione_separata,
            quota_carico_utente=excluded.quota_carico_utente,
            soglia_bollo=excluded.soglia_bollo,
            valore_bollo=excluded.valore_bollo
        """
        cursor.execute(query, (user_id, anno, soglia, aliquota, quota, s_bollo, v_bollo))
        conn.commit()
        conn.close()
    
    # --- GESTIONE CLIENTI ---
    def get_clients(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients WHERE user_id = ? ORDER BY ragione_sociale ASC", (user_id,))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_client_by_id(self, client_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def save_client(self, user_id, client_id, ragione_sociale, piva_cf, indirizzo, email, sostituto, note):
        conn = self._get_connection()
        cursor = conn.cursor()
        if client_id:
            query = """UPDATE clients SET 
                       ragione_sociale=?, piva_cf=?, indirizzo=?, email_amministrazione=?, sostituto_imposta=?, note=? 
                       WHERE id=? AND user_id=?"""
            cursor.execute(query, (ragione_sociale, piva_cf, indirizzo, email, sostituto, note, client_id, user_id))
        else:
            query = """INSERT INTO clients 
                       (user_id, ragione_sociale, piva_cf, indirizzo, email_amministrazione, sostituto_imposta, note) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)"""
            cursor.execute(query, (user_id, ragione_sociale, piva_cf, indirizzo, email, sostituto, note))
        conn.commit()
        conn.close()

    def delete_client(self, client_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
        conn.close()

    # --- GESTIONE INCARICHI ---
    def get_assignments(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        query = """SELECT a.*, c.ragione_sociale 
                   FROM assignments a 
                   JOIN clients c ON a.client_id = c.id 
                   WHERE a.user_id = ? 
                   ORDER BY a.data_inizio DESC"""
        cursor.execute(query, (user_id,))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_assignment_by_id(self, assign_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM assignments WHERE id = ?", (assign_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def save_assignment(self, user_id, assign_id, client_id, descrizione, data_inizio, rif_det, data_det, rup, email_rup, cig, stato):
        conn = self._get_connection()
        cursor = conn.cursor()
        if assign_id:
            query = """UPDATE assignments SET 
                       client_id=?, descrizione_progetto=?, data_inizio=?, rif_determina_incarico=?, 
                       data_determina=?, nome_rup=?, email_rup=?, cig=?, stato=? 
                       WHERE id=? AND user_id=?"""
            cursor.execute(query, (client_id, descrizione, data_inizio, rif_det, data_det, rup, email_rup, cig, stato, assign_id, user_id))
        else:
            query = """INSERT INTO assignments 
                       (user_id, client_id, descrizione_progetto, data_inizio, rif_determina_incarico, data_determina, nome_rup, email_rup, cig, stato) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            cursor.execute(query, (user_id, client_id, descrizione, data_inizio, rif_det, data_det, rup, email_rup, cig, stato))
        conn.commit()
        conn.close()

    def delete_assignment(self, assign_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM assignments WHERE id = ?", (assign_id,))
        conn.commit()
        conn.close()

    # --- GESTIONE RICEVUTE ---
    def get_annual_gross(self, user_id, year):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(importo_lordo) FROM receipts WHERE user_id = ? AND anno_riferimento = ?", (user_id, year))
        result = cursor.fetchone()[0]
        conn.close()
        return result if result else 0.00

    def get_receipts(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        query = """
            SELECT r.*, c.ragione_sociale 
            FROM receipts r
            JOIN assignments a ON r.assignment_id = a.id
            JOIN clients c ON a.client_id = c.id
            WHERE r.user_id = ?
            ORDER BY r.numero_progressivo DESC, r.data_emissione DESC
        """
        cursor.execute(query, (user_id,))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_next_receipt_number(self, user_id, year):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(numero_progressivo) FROM receipts WHERE user_id = ? AND anno_riferimento = ?", (user_id, year))
        res = cursor.fetchone()[0]
        conn.close()
        return (res + 1) if res else 1

    def save_receipt(self, user_id, assignment_id, numero, anno, data_em, desc, 
                     lordo, imp_inps, aliq_inps, rit_inps, quota_inps_user,
                     aliq_irpef, imp_irpef, rimborsi, bollo_bool, val_bollo, netto, path_pdf):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO receipts 
            (user_id, assignment_id, numero_progressivo, anno_riferimento, data_emissione, descrizione_prestazione,
             importo_lordo, imponibile_inps, aliquota_inps_applicata, ritenuta_inps_totale, quota_inps_utente,
             aliquota_ritenuta_acconto, importo_ritenuta_acconto, rimborso_spese_esenti, 
             bollo_applicato, importo_bollo, netto_a_pagare, file_path_pdf)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (
            user_id, assignment_id, numero, anno, data_em, desc,
            lordo, imp_inps, aliq_inps, rit_inps, quota_inps_user,
            aliq_irpef, imp_irpef, rimborsi,
            bollo_bool, val_bollo, netto, path_pdf
        ))
        conn.commit()
        conn.close()
    
    def get_receipt_path(self, receipt_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT file_path_pdf FROM receipts WHERE id = ?", (receipt_id,))
        result = cursor.fetchone()
        conn.close()
        return result['file_path_pdf'] if result else None

    def get_receipt_by_id(self, receipt_id):
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row['id'],
                "user_id": row['user_id'],
                "assign_id": row['assignment_id'],
                "numero": row['numero_progressivo'],
                "anno": row['anno_riferimento'],
                "data": row['data_emissione'],
                "desc": row['descrizione_prestazione'],
                "lordo": row['importo_lordo'],
                "imp_inps": row['imponibile_inps'],
                "aliq_inps": row['aliquota_inps_applicata'],
                "rit_inps": row['ritenuta_inps_totale'],
                "quota_inps": row['quota_inps_utente'],
                "aliq_irpef": row['aliquota_ritenuta_acconto'],
                "imp_irpef": row['importo_ritenuta_acconto'],
                "spese": row['rimborso_spese_esenti'],
                "bollo_bool": row['bollo_applicato'],
                "val_bollo": row['importo_bollo'],
                "netto": row['netto_a_pagare'],
                "filename": row['file_path_pdf']
            }
        return None

# Istanza globale
db = DatabaseHandler()


# =========================================================================
# MODULO 2: PDF GENERATOR
# =========================================================================

class RicevutaPDF(FPDF):
    def __init__(self, is_credit_note=False, *args, **kwargs):
        self.is_credit_note = is_credit_note
        super().__init__(*args, **kwargs)

    def header(self):
        if self.page_no() == 1:
            self.set_font('Helvetica', 'B', 16)
            # TITOLO DINAMICO
            title = "NOTA DI CREDITO (Storno)" if self.is_credit_note else "RICEVUTA PRESTAZIONE OCCASIONALE"
            self.cell(180, 10, title, align='C', new_x="LMARGIN", new_y="NEXT")
            self.set_font('Helvetica', 'I', 10)
            self.cell(180, 5, '(art. 2222 e succ. Codice Civile)', align='C', new_x="LMARGIN", new_y="NEXT")
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', align='C')

def genera_pdf_ricevuta(profile, client, receipt_data, filename, is_credit_note=False):
    # CONFIGURAZIONE SICURA
    MARGIN = 15
    CONTENT_WIDTH = 180 
    
    # Passiamo il flag alla classe PDF
    pdf = RicevutaPDF(is_credit_note=is_credit_note, orientation='P', unit='mm', format='A4')
    pdf.set_margins(left=MARGIN, top=MARGIN, right=MARGIN)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    def reset_x():
        pdf.set_x(MARGIN)

    # --- HELPER: FORMATTAZIONE ITALIANA ---
    def to_ita(num):
        """Converte un float in stringa formato Italia: 1.234,56"""
        try:
            # Prima formatta all'inglese (virgola migliaia, punto decimali)
            s = f"{float(num):,.2f}"
            # Scambia i simboli usando un placeholder temporaneo
            return s.replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return "0,00"

    # =========================================================================
    # PAGINA 1: RICEVUTA
    # =========================================================================

    # 1. Dati Emittente
    reset_x()
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(CONTENT_WIDTH, 6, "EMITTENTE:", new_x="LMARGIN", new_y="NEXT", align='L')
    
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(CONTENT_WIDTH, 5, f"{profile['nome_completo']}", new_x="LMARGIN", new_y="NEXT", align='L')
    pdf.cell(CONTENT_WIDTH, 5, f"C.F.: {profile['codice_fiscale']}", new_x="LMARGIN", new_y="NEXT", align='L')
    pdf.cell(CONTENT_WIDTH, 5, f"{profile['indirizzo']}", new_x="LMARGIN", new_y="NEXT", align='L')
    pdf.ln(5)
    
    # 2. Dati Committente
    reset_x()
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(CONTENT_WIDTH, 6, "COMMITTENTE:", new_x="LMARGIN", new_y="NEXT", align='L')
    
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(CONTENT_WIDTH, 5, f"{client['ragione_sociale']}", new_x="LMARGIN", new_y="NEXT", align='L')
    pdf.cell(CONTENT_WIDTH, 5, f"P.IVA/C.F.: {client['piva_cf']}", new_x="LMARGIN", new_y="NEXT", align='L')
    pdf.cell(CONTENT_WIDTH, 5, f"{client['indirizzo']}", new_x="LMARGIN", new_y="NEXT", align='L')
    pdf.ln(8)
    
    # 3. Dettagli Ricevuta
    reset_x()
    col_width = CONTENT_WIDTH / 2 
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Helvetica', 'B', 11)
    
    pdf.cell(col_width, 8, f"N. {receipt_data['numero']}/{receipt_data['anno']}", border=1, fill=True, align='L')
    pdf.cell(col_width, 8, f"Data: {receipt_data['data']}", border=1, fill=True, new_x="LMARGIN", new_y="NEXT", align='L')
    
    pdf.ln(5)
    
    # 4. Descrizione e Progetto (Struttura a Tabella Dinamica)
    reset_x()
    
    # RIGA 1: Intestazione
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(CONTENT_WIDTH, 8, "Oggetto della prestazione:", new_x="LMARGIN", new_y="NEXT", align='L')
    
    # RIGA 2: Descrizione Principale (Con Bordo)
    pdf.set_font('Helvetica', '', 10)
    reset_x()
    # multi_cell gestisce automaticamente il testo lungo andando a capo dentro il box
    pdf.multi_cell(CONTENT_WIDTH, 5, receipt_data['desc'], border=1, align='L')
    
    # Preparazione dati "Info Extra"
    project_text = f"Progetto: {receipt_data['progetto_macro']}" if receipt_data.get('progetto_macro') else None
    
    codes = []
    if receipt_data.get('cig'): codes.append(f"CIG: {receipt_data['cig']}")
    if receipt_data.get('rup'): codes.append(f"RUP: {receipt_data['rup']}")
    if receipt_data.get('rif_det'): codes.append(f"Rif: {receipt_data['rif_det']}")
    codes_text = " | ".join(codes) if codes else None

    # Se ci sono info extra, cambiamo font e scriviamo le "righe" della tabella invisibile
    if project_text or codes_text:
        pdf.set_font('Helvetica', 'I', 9)
        pdf.ln(1) # Un piccolo respiro grafico dopo il box principale
        
        # RIGA 3: Progetto (Senza Bordo, Tabella Invisibile)
        if project_text:
            reset_x()
            pdf.multi_cell(CONTENT_WIDTH, 5, project_text, border=0, align='L')
        
        # RIGA 4: Codici (Senza Bordo, Tabella Invisibile)
        if codes_text:
            reset_x()
            pdf.multi_cell(CONTENT_WIDTH, 5, codes_text, border=0, align='L')

    pdf.ln(5)

    # 5. Tabella Importi
    w_label = CONTENT_WIDTH * 0.75
    w_value = CONTENT_WIDTH * 0.25

    def row(label, value, bold=False):
        reset_x()
        pdf.set_font('Helvetica', 'B' if bold else '', 10)
        pdf.cell(w_label, 7, label, border=1, align='L')
        # USIAMO to_ita() PER LA FORMATTAZIONE
        pdf.cell(w_value, 7, f"EUR {to_ita(value)}", border=1, align='R', new_x="LMARGIN", new_y="NEXT")

    reset_x()
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(w_label, 7, "VOCI", border=1, fill=True, align='C')
    pdf.cell(w_value, 7, "IMPORTO", border=1, fill=True, align='C', new_x="LMARGIN", new_y="NEXT")

    # Righe
    row("Compenso LORDO", receipt_data['lordo'])
    
    if receipt_data['spese'] != 0:
        row("Rimborso Spese (Esenti)", receipt_data['spese'])

    if receipt_data['imp_irpef'] != 0:
        # Gestione segno per Ritenuta
        val_ritenuta = -abs(receipt_data['imp_irpef'])
        if is_credit_note:
             # In nota credito storniamo (valore positivo se era negativo o viceversa in base a come salvato)
             # Qui prendiamo il valore raw dal DB/calcolo
             val_ritenuta = receipt_data['imp_irpef']
        
        row(f"Ritenuta d'Acconto ({receipt_data['aliq_irpef']:.0f}%)", val_ritenuta)
    
    if receipt_data['quota_inps'] != 0:
        val_inps = -abs(receipt_data['quota_inps'])
        if is_credit_note:
            val_inps = receipt_data['quota_inps']
        row("Trattenuta INPS (Gestione Separata 1/3)", val_inps)

    # Bollo
    if receipt_data['val_bollo'] != 0:
        row("Imposta di Bollo (Rivalsa)", receipt_data['val_bollo'])

    # Totale Netto
    reset_x()
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(w_label, 10, "NETTO DA PAGARE", border=1, align='L')
    pdf.cell(w_value, 10, f"EUR {to_ita(receipt_data['netto'])}", border=1, align='R', new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    # 6. Note Fiscali
    reset_x()
    pdf.set_font('Helvetica', '', 8) 
    
    reset_x()
    if receipt_data['imp_irpef'] == 0:
        pdf.multi_cell(CONTENT_WIDTH, 4, "* Prestazione non soggetta a ritenuta d'acconto.", align='L')
    else:
         pdf.multi_cell(CONTENT_WIDTH, 4, "* Ritenuta d'acconto da versare tramite F24 (Cod. Tributo 1040) entro il 16 del mese successivo.", align='L')
    
    reset_x()
    if receipt_data['val_bollo'] > 0:
        pdf.multi_cell(CONTENT_WIDTH, 4, "** Imposta di bollo di 2,00 euro assolta sull'originale.", align='L')
    elif receipt_data['val_bollo'] < 0:
        pdf.multi_cell(CONTENT_WIDTH, 4, "** Storno imposta di bollo applicata in origine.", align='L')
    else:
        pdf.multi_cell(CONTENT_WIDTH, 4, "** Esente da imposta di bollo (importo inferiore a 77,47 euro).", align='L')

    if float(receipt_data['quota_inps']) != 0:
         reset_x()
         pdf.multi_cell(CONTENT_WIDTH, 4, "*** Applicata trattenuta INPS Gestione Separata (L. 335/95).", align='L')

    pdf.ln(8)

    # 7. Firma
    reset_x()
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(CONTENT_WIDTH, 5, f"Pagamento tramite bonifico su IBAN: {profile['iban']}", align='L')
    
    pdf.ln(10)
    
    reset_x()
    pdf.set_x(MARGIN + 90)
    pdf.cell(90, 5, "Firma", align='C', new_x="LMARGIN", new_y="NEXT")
    
    reset_x()
    pdf.set_x(MARGIN + 90)
    pdf.cell(90, 15, "_______________________", align='C', new_x="LMARGIN", new_y="NEXT")


    # =========================================================================
    # PAGINA 2: DICHIARAZIONE
    # =========================================================================
    pdf.add_page()
    
    reset_x()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.multi_cell(CONTENT_WIDTH, 8, "DICHIARAZIONE SOSTITUTIVA DELL'ATTO DI NOTORIETA'", align='C')
    pdf.set_font('Helvetica', 'I', 10)
    pdf.cell(CONTENT_WIDTH, 6, "(Art. 47 D.P.R. 28 dicembre 2000, n. 445)", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    reset_x()
    pdf.set_font('Helvetica', '', 10)
    intro_text = (
        f"Il sottoscritto {profile['nome_completo']}, Codice Fiscale {profile['codice_fiscale']}, "
        f"residente in {profile['indirizzo']}, "
        "consapevole delle sanzioni penali richiamate dall'art. 76 del D.P.R. 445/2000 in caso di dichiarazioni mendaci,"
    )
    pdf.multi_cell(CONTENT_WIDTH, 5, intro_text, align='L')
    
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(CONTENT_WIDTH, 6, "DICHIARA", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(CONTENT_WIDTH, 6, "sotto la propria responsabilità:", align='L', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    punti = [
        "1) che la prestazione resa ha carattere del tutto occasionale non svolgendo il sottoscritto prestazione di lavoro autonomo con carattere di abitualità;",
        "2) di essere dipendente di ruolo e a tempo pieno della Provincia di Salerno area Funzionari ed EQ;",
        "3) la prestazione oggetto della presente nota è stata effettuata in via occasionale, contingente ed episodica; il relativo compenso è da inquadrare tra i redditi di cui all'art. 81 comma 1, lettera L, del D.P.R. 917/86 e, pertanto, esclusa dal campo di applicazione dell'I.V.A. ai sensi dell'art. 5 del D.P.R. n. 633 del 26 ottobre 1972;",
        "4) di non essere soggetto al regime Iva a norma dell'ex art. 5, comma 2, D.P.R. 633/72;"
    ]

    for p in punti:
        reset_x()
        pdf.multi_cell(CONTENT_WIDTH, 5, p, align='L')
        pdf.ln(2)

    # Punto 5 Dinamico
    imponibile = receipt_data['imp_inps']
    totale_inps = receipt_data['rit_inps'] 
    
    if imponibile > 0:
        testo_p5 = (
            "5) di avere fruito nell'anno, ai fini contributivi, della franchigia prevista dall'art. 44 del D.L. 30 settembre 2003, n. 269 "
            f"e l'importo da assoggettare a ritenuta INPS del 24% è pari a EUR {to_ita(imponibile)}. "
            f"Pertanto, l'importo complessivo che codesta stazione appaltante dovrà versare all'INPS alla Gestione Separata dello scrivente "
            f"aperta dal 30/10/2008 è pari a EUR {to_ita(totale_inps)} comprensivo dell'importo detratto in fattura."
        )
    elif imponibile < 0:
        testo_p5 = (
            f"5) che la presente nota è a storno parziale o totale di redditi precedentemente dichiarati. Imponibile INPS stornato: EUR {to_ita(imponibile)}."
        )
    else:
        testo_p5 = (
            "5) di non avere fruito nell'anno, ai fini contributivi, della franchigia prevista dall'art. 44 del D.L. 30 settembre 2003, n. 269."
        )

    reset_x()
    pdf.multi_cell(CONTENT_WIDTH, 5, testo_p5, align='L')
    pdf.ln(15)

    reset_x()
    pdf.set_x(MARGIN + 90)
    pdf.cell(90, 5, "In fede", align='C', new_x="LMARGIN", new_y="NEXT")
    
    reset_x()
    pdf.set_x(MARGIN + 90)
    pdf.cell(90, 15, "_______________________", align='C', new_x="LMARGIN", new_y="NEXT")

    if not os.path.exists("RPO_RICEVUTE"):
        os.makedirs("RPO_RICEVUTE")
        
    pdf.output(filename)
    return filename # <--- Assicurati che ci sia questa riga!


# =========================================================================
# MODULO 3: INTERFACCIA GRAFICA (GUI)
# =========================================================================

# =========================================================================
# CLASSE LOGIN WINDOW
# =========================================================================
class LoginWindow:
    def __init__(self, root, on_login_success):
        self.root = root
        self.on_login_success = on_login_success
        self.root.title("RPO Zero - Accesso")
        self.root.geometry("400x500")
        self.root.resizable(False, False)
        
        # Stile base - MODIFICA QUI
        style = ttk.Style()
        sistema = platform.system()
        try:
            if sistema == 'Darwin':      # macOS
                style.theme_use('default')  # Tema default funziona meglio su Mac
                # Configura colori espliciti per evitare problemi
                style.configure("TEntry", fieldbackground="white")
                style.configure("TCombobox", fieldbackground="white")
            elif sistema == 'Windows':   # Windows
                style.theme_use('vista')
            else:                        # Linux
                style.theme_use('clam')
        except:
            style.theme_use('default')
        
        style.configure("Big.TButton", font=('Arial', 10, 'bold'), padding=8)

        self.frame = ttk.Frame(root, padding=30)
        # ... resto del codice ...
        self.frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(self.frame, text="RPO Zero", font=("Arial", 22, "bold"), foreground="#333").pack(pady=(0, 5))
        ttk.Label(self.frame, text="Multi-Utente", font=("Arial", 10), foreground="gray").pack(pady=(0, 30))

        # Form Login - NUOVO: Selezione Utente
        ttk.Label(self.frame, text="Seleziona Utente").pack(anchor="w")
        self.cmb_user = ttk.Combobox(self.frame, font=("Arial", 11), state="readonly")
        self.cmb_user.pack(fill=tk.X, pady=(5, 5))
        self.cmb_user.bind("<<ComboboxSelected>>", self.on_user_selected)
        
        ttk.Label(self.frame, text="Username").pack(anchor="w", pady=(10, 0))
        self.ent_user = ttk.Entry(self.frame, font=("Arial", 11), state="readonly")
        self.ent_user.pack(fill=tk.X, pady=(5, 15))

        ttk.Label(self.frame, text="Password").pack(anchor="w")
        self.ent_pass = ttk.Entry(self.frame, show="*", font=("Arial", 11))
        self.ent_pass.pack(fill=tk.X, pady=(5, 20))

        ttk.Button(self.frame, text="ACCEDI", style="Big.TButton", command=self.do_login).pack(fill=tk.X, pady=10)
        
        ttk.Separator(self.frame).pack(fill=tk.X, pady=20)
        
        ttk.Label(self.frame, text="Non hai un account?", foreground="gray").pack()
        ttk.Button(self.frame, text="Registra Nuovo Utente", command=self.open_register_window).pack(pady=5)

        # IMPORTANTE: Carica utenti DOPO aver creato tutti i widget
        self.load_users()

    def load_users(self):
        """Carica la lista degli utenti dal database"""
        conn = db._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, display_name FROM users ORDER BY display_name")
        users = cur.fetchall()
        conn.close()
        
        # Crea mappa: display_name -> (id, username)
        self.user_map = {}
        display_names = []
        for user in users:
            display = user['display_name'] if user['display_name'] else user['username']
            display_names.append(display)
            self.user_map[display] = (user['id'], user['username'])
        
        self.cmb_user['values'] = display_names
        if display_names:
            self.cmb_user.current(0)
            self.on_user_selected(None)

    def on_user_selected(self, event):
        """Quando si seleziona un utente, popola automaticamente lo username"""
        selected = self.cmb_user.get()
        if selected and selected in self.user_map:
            _, username = self.user_map[selected]
            self.ent_user.config(state="normal")
            self.ent_user.delete(0, tk.END)
            self.ent_user.insert(0, username)
            self.ent_user.config(state="readonly")
            self.ent_pass.focus()

    def do_login(self):
        u = self.ent_user.get().strip()
        p = self.ent_pass.get().strip()
        if not u or not p:
            messagebox.showwarning("Attenzione", "Inserisci username e password")
            return

        user_data = db.login_user(u, p)
        if user_data:
            user_id = user_data['id']
            user_name = user_data['display_name']
            self.frame.destroy()
            self.on_login_success(user_id, user_name)
        else:
            messagebox.showerror("Errore", "Credenziali non valide")

    def open_register_window(self):
        reg = tk.Toplevel(self.root)
        # reg.configure(bg='white')  # Aggiungi questa riga
        reg.title("Registrazione")
        reg.geometry("350x400")
        reg.transient(self.root)
        reg.grab_set()
       
        ttk.Label(reg, text="Nuovo Utente", font=("Arial", 14, "bold")).pack(pady=15)
        
        frm = ttk.Frame(reg, padding=20)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Username *").pack(anchor="w"); e_u = ttk.Entry(frm); e_u.pack(fill=tk.X, pady=5)
        ttk.Label(frm, text="Password *").pack(anchor="w"); e_p = ttk.Entry(frm, show="*"); e_p.pack(fill=tk.X, pady=5)
        ttk.Label(frm, text="Nome da visualizzare").pack(anchor="w"); e_n = ttk.Entry(frm); e_n.pack(fill=tk.X, pady=5)

        def do_reg():
            if not e_u.get() or not e_p.get():
                messagebox.showwarning("Err", "Campi obbligatori")
                return
            if db.register_user(e_u.get(), e_p.get(), e_n.get()):
                messagebox.showinfo("OK", "Utente creato! Ora fai il login.")
                reg.destroy()
                self.load_users()  # Ricarica la lista utenti
            else:
                messagebox.showerror("Errore", "Username già esistente.")

        ttk.Button(frm, text="Registrati", command=do_reg).pack(pady=20, fill=tk.X)

# =========================================================================
# CLASSE APP PRINCIPALE
# =========================================================================
class GestionaleRicevuteApp:
    def __init__(self, root, user_id, user_name):
        self.root = root
        self.user_id = user_id
        self.user_name = user_name
        
        self.root.title(f"RPO Zero - {self.user_name}")
        self.root.geometry("1150x850")
        
        # --- Configurazione Stile --- MODIFICA QUI
        self.style = ttk.Style()
        sistema = platform.system()
        try:
            if sistema == 'Darwin':      # macOS
                self.style.theme_use('default')  # Tema default funziona meglio su Mac
                # Configura colori espliciti per evitare problemi
                self.style.configure("TEntry", fieldbackground="white")
                self.style.configure("TCombobox", fieldbackground="white")
            elif sistema == 'Windows':   # Windows
                self.style.theme_use('vista')
            else:                        # Linux
                self.style.theme_use('clam')
        except:
            self.style.theme_use('default')
        
        self.style.configure("Treeview", rowheight=30, font=('Arial', 10))
        # ... resto del codice ...
        self.style.configure("Treeview.Heading", font=('Arial', 10, 'bold'), background="#e1e1e1")
        self.style.configure("TButton", font=('Arial', 10), padding=6)
        self.style.configure("Big.TButton", font=('Arial', 10, 'bold'), padding=8)
        self.style.configure("Green.TButton", foreground="darkgreen", font=('Arial', 10, 'bold'), padding=8)
        self.style.configure("Red.TButton", foreground="darkred", font=('Arial', 10, 'bold'), padding=8)

        self.current_calc = {} 

        # Auto-config anno per QUESTO utente
        current_year = date.today().year
        db.ensure_fiscal_config_exists(self.user_id, current_year)

        # Frame Principale# Frame Principale - usa tk.Frame con sfondo bianco
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        self.check_start()

    def open_pdf(self, filepath):
        """Versione blindata per risolvere WinError 2"""
        import platform
        import subprocess
        import os
        import time

        try:
            # 1. TRASFORMAZIONE IN PERCORSO ASSOLUTO (Cruciale per Windows/Dropbox)
            path_assoluto = os.path.abspath(filepath)
            
            # 2. ATTESA DI SICUREZZA (0.5 secondi)
            # Diamo tempo al sistema operativo di 'rilasciare' il file appena scritto
            time.sleep(0.5)

            if not os.path.exists(path_assoluto):
                messagebox.showerror("Errore", f"File non trovato: {path_assoluto}")
                return

            system = platform.system()
            if system == 'Darwin':       # macOS
                subprocess.call(['open', path_assoluto])
            elif system == 'Windows':    # Windows
                # Usiamo os.startfile con il percorso assoluto normalizzato
                os.startfile(os.path.normpath(path_assoluto))
            else:                        # Linux
                subprocess.call(['xdg-open', path_assoluto])
                
        except Exception as e:
            messagebox.showerror("Errore Apertura", f"Dettaglio errore: {e}")

    def clear_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def check_start(self):
        try:
            # Passiamo user_id
            profile = db.get_user_profile(self.user_id)
            if profile:
                self.show_dashboard(profile)
            else:
                self.show_setup()
        except Exception as e:
            messagebox.showerror("Errore Critico", f"Errore DB: {e}")

    # =========================================================================
    # SCHEDA PROFILO - LAYOUT OTTIMIZZATO (VERSIONE 2.1.0)
    # =========================================================================
    def show_setup(self):
        self.clear_frame()
        existing = db.get_user_profile(self.user_id)
        
        # Header coerente con le altre sezioni
        self.create_header_back("Configurazione Profilo Professionale", 
                               self.show_dashboard if existing else None, None)

        # Contenitore principale che eredita il colore del sistema
        form_frame = ttk.Frame(self.main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True, pady=20)

        ttk.Label(form_frame, text="Inserisci i dati che appariranno nelle ricevute", 
                  font=("Arial", 10, "italic"), foreground="gray").pack(anchor="w", pady=(0, 20))

        fields = [
            ("Nome Completo *:", "nome"),
            ("Codice Fiscale *:", "cf"),
            ("Indirizzo Completo *:", "indirizzo"),
            ("IBAN *:", "iban"),
            ("Email di contatto:", "email"),
            ("Telefono:", "telefono")
        ]

        self.profile_vars = {}
        for lbl_text, key in fields:
            row = ttk.Frame(form_frame)
            row.pack(fill=tk.X, pady=5)
            
            # Label con larghezza fissa per allineamento
            ttk.Label(row, text=lbl_text, width=30, font=("Arial", 10, "bold")).pack(side=tk.LEFT)
            
            # Entry che si espande per occupare tutto lo spazio a destra
            e = ttk.Entry(row, font=("Arial", 10))
            e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
            self.profile_vars[key] = e

        # Popolamento dati esistenti
        if existing:
            mapping = {
                "nome": "nome_completo", "cf": "codice_fiscale", 
                "indirizzo": "indirizzo", "iban": "iban", 
                "email": "email", "telefono": "telefono"
            }
            for key, db_key in mapping.items():
                if existing[db_key]:
                    self.profile_vars[key].insert(0, existing[db_key])

        # Area pulsante centrata
        btn_area = ttk.Frame(form_frame)
        btn_area.pack(fill=tk.X, pady=40)
        
        ttk.Button(btn_area, text="💾 Salva Profilo Professionale", 
                   style="Big.TButton", command=self.save_setup_data).pack()

    def save_setup_data(self):
        # Recupero dati e pulizia spazi
        nome = self.profile_vars["nome"].get().strip()
        cf = self.profile_vars["cf"].get().strip()
        indirizzo = self.profile_vars["indirizzo"].get().strip()
        iban = self.profile_vars["iban"].get().strip()
        email = self.profile_vars["email"].get().strip()
        telefono = self.profile_vars["telefono"].get().strip()

        # Validazione campi obbligatori
        if not all([nome, cf, indirizzo, iban]):
            messagebox.showerror("Errore", "I campi contrassegnati con * sono obbligatori.")
            return

        try:
            db.save_user_profile(self.user_id, nome, cf, indirizzo, iban, email, telefono)
            messagebox.showinfo("Successo", "Profilo aggiornato con successo.")
            self.check_start() # Ritorna alla Dashboard
        except Exception as e:
            messagebox.showerror("Errore DB", f"Impossibile salvare il profilo: {e}")

    # =========================================================================
    # SEZIONE 2: DASHBOARD
    # =========================================================================
    def show_dashboard(self, profile):
        self.clear_frame()
        
        header = ttk.Frame(self.main_frame)
        header.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(header, text=f"Dashboard - {profile['nome_completo']}", font=("Arial", 18, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="⚙️ Profilo", command=self.show_setup).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header, text="Configurazione Fiscale", command=self.show_fiscal_config).pack(side=tk.RIGHT, padx=5)
        
        # MODIFICA: usa tk.Frame invece di ttk.Frame per il grid
        grid = ttk.Frame(self.main_frame)
        grid.pack(fill=tk.BOTH, expand=True)
        
        def card(parent, text, command, row, col, color="#4CAF50"):
            f = ttk.Frame(parent, relief='solid', borderwidth=1)
            f.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")
            
            # Frame interno colorato per il titolo
            header = tk.Frame(f, bg=color)
            header.pack(fill=tk.BOTH, expand=True)
            
            tk.Label(header, text=text, bg=color, fg="white", font=("Arial", 14, "bold"), wraplength=200).pack(pady=20)
            
            ttk.Button(header, text="Apri", command=command).pack(pady=(0,20))
        
        card(grid, "👥 Gestione Clienti", self.show_clients_list, 0, 0, "#3D3175")
        card(grid, "📁 Gestione Incarichi", self.show_assignments_list, 0, 1, "#AA5239")
        card(grid, "📄 Nuova Ricevuta", self.show_receipt_form, 1, 0, "#28784D")
        card(grid, "📚 Storico Ricevute", self.show_receipts_history, 1, 1, "#AA9439")
        
        for i in range(2): grid.columnconfigure(i, weight=1)
        for i in range(2): grid.rowconfigure(i, weight=1)
    # =========================================================================
    # SEZIONE 3: CONFIGURAZIONE FISCALE
    # =========================================================================
    def show_fiscal_config(self):
        self.clear_frame()
        self.create_header_back("Configurazione Fiscale Anno Corrente", self.show_dashboard, None)

        current_year = date.today().year
        config = db.get_fiscal_config(self.user_id, current_year)

        form_frame = ttk.Frame(self.main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True, pady=20)

        fields = [
            ("Soglia Franchigia INPS (€):", "soglia", config['soglia_inps_no_tax'] if config else 5000.00),
            ("Aliquota INPS Gestione Separata (%):", "aliq", config['aliquota_gestione_separata'] if config else 24.00),
            ("Quota Utente (0.33 = 1/3):", "quota", config['quota_carico_utente'] if config else 0.3333),
            ("Soglia Bollo (€):", "s_bollo", config['soglia_bollo'] if config else 77.47),
            ("Valore Bollo (€):", "v_bollo", config['valore_bollo'] if config else 2.00),
        ]

        self.fiscal_vars = {}
        for lbl_text, key, default_val in fields:
            row = ttk.Frame(form_frame)
            row.pack(fill=tk.X, pady=5)
            ttk.Label(row, text=lbl_text, width=35).pack(side=tk.LEFT)
            e = ttk.Entry(row)
            e.insert(0, str(default_val))
            e.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.fiscal_vars[key] = e

        def save_fiscal():
            try:
                db.save_fiscal_config(self.user_id, current_year,
                    float(self.fiscal_vars["soglia"].get()),
                    float(self.fiscal_vars["aliq"].get()),
                    float(self.fiscal_vars["quota"].get()),
                    float(self.fiscal_vars["s_bollo"].get()),
                    float(self.fiscal_vars["v_bollo"].get()))
                messagebox.showinfo("Successo", "Configurazione salvata")
                self.check_start() # Ritorna alla Dashboard
            except ValueError:
                messagebox.showerror("Errore", "Valori non validi")

        ttk.Button(form_frame, text="Salva", style="Big.TButton", command=save_fiscal).pack(pady=20)

    # =========================================================================
    # SEZIONE 4: CLIENTI
    # =========================================================================
    def show_clients_list(self):
        self.clear_frame()
        self.create_header_back("Gestione Clienti", self.show_client_form, "+ Nuovo Cliente")

        cols = ("ragione", "piva", "indirizzo")
        tree = ttk.Treeview(self.main_frame, columns=cols, show="headings")
        tree.heading("ragione", text="Ragione Sociale")
        tree.heading("piva", text="P.IVA/C.F.")
        tree.heading("indirizzo", text="Indirizzo")
        tree.column("ragione", width=300)
        tree.column("piva", width=150)
        tree.column("indirizzo", width=300)
        tree.pack(fill=tk.BOTH, expand=True, pady=10)

        for c in db.get_clients(self.user_id):
            tree.insert("", tk.END, iid=c['id'], values=(c['ragione_sociale'], c['piva_cf'], c['indirizzo']))

        self.create_crud_buttons(tree, self.show_client_form, db.delete_client, self.show_clients_list)

    def show_client_form(self, client_id):
        self.clear_frame()
        existing = db.get_client_by_id(client_id) if client_id else None
        title = "Modifica Cliente" if existing else "Nuovo Cliente"
        self.create_header_back(title, self.show_clients_list, None)

        form = ttk.Frame(self.main_frame)
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        fields = [
            ("Ragione Sociale *:", "ragione"),
            ("P.IVA / C.F. *:", "piva"),
            ("Indirizzo *:", "indirizzo"),
            ("Email Amministrazione:", "email"),
            ("Note:", "note")
        ]

        self.client_vars = {}
        for lbl, key in fields:
            row = ttk.Frame(form)
            row.pack(fill=tk.X, pady=5)
            ttk.Label(row, text=lbl, width=25, anchor="w").pack(side=tk.LEFT)
            if key == "note":
                txt = tk.Text(row, height=4, font=("Arial", 10))
                txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                self.client_vars[key] = txt
            else:
                e = ttk.Entry(row)
                e.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.client_vars[key] = e

        check_row = ttk.Frame(form)
        check_row.pack(fill=tk.X, pady=5)
        ttk.Label(check_row, text="È Sostituto d'Imposta:", width=25, anchor="w").pack(side=tk.LEFT)
        self.client_vars["sostituto"] = tk.BooleanVar()
        ttk.Checkbutton(check_row, variable=self.client_vars["sostituto"]).pack(side=tk.LEFT)

        if existing:
            self.client_vars["ragione"].insert(0, existing['ragione_sociale'])
            self.client_vars["piva"].insert(0, existing['piva_cf'])
            self.client_vars["indirizzo"].insert(0, existing['indirizzo'])
            self.client_vars["email"].insert(0, existing['email_amministrazione'] or "")
            self.client_vars["note"].insert("1.0", existing['note'] or "")
            self.client_vars["sostituto"].set(existing['sostituto_imposta'])

        def save():
            if not all([self.client_vars["ragione"].get(), self.client_vars["piva"].get(), self.client_vars["indirizzo"].get()]):
                messagebox.showerror("Errore", "Compila i campi obbligatori")
                return
            try:
                db.save_client(self.user_id, client_id, 
                    self.client_vars["ragione"].get(),
                    self.client_vars["piva"].get(),
                    self.client_vars["indirizzo"].get(),
                    self.client_vars["email"].get(),
                    self.client_vars["sostituto"].get(),
                    self.client_vars["note"].get("1.0", tk.END).strip())
                messagebox.showinfo("OK", "Cliente salvato")
                self.show_clients_list()
            except Exception as e:
                messagebox.showerror("Errore", str(e))

        self.create_save_cancel_btns(lambda _: save(), self.show_clients_list, None)

    # =========================================================================
    # SEZIONE 5: INCARICHI
    # =========================================================================
    def show_assignments_list(self):
        self.clear_frame()
        self.create_header_back("Gestione Incarichi", self.show_assignment_form, "+ Nuovo Incarico")

        cols = ("cliente", "progetto", "data", "stato")
        tree = ttk.Treeview(self.main_frame, columns=cols, show="headings")
        tree.heading("cliente", text="Cliente")
        tree.heading("progetto", text="Progetto")
        tree.heading("data", text="Data Inizio")
        tree.heading("stato", text="Stato")
        tree.column("cliente", width=200)
        tree.column("progetto", width=300)
        tree.column("data", width=100)
        tree.column("stato", width=100)
        tree.pack(fill=tk.BOTH, expand=True, pady=10)

        for a in db.get_assignments(self.user_id):
            tree.insert("", tk.END, iid=a['id'], values=(
                a['ragione_sociale'], a['descrizione_progetto'], a['data_inizio'], a['stato']))

        self.create_crud_buttons(tree, self.show_assignment_form, db.delete_assignment, self.show_assignments_list)

    def show_assignment_form(self, assign_id):
        self.clear_frame()
        existing = db.get_assignment_by_id(assign_id) if assign_id else None
        title = "Modifica Incarico" if existing else "Nuovo Incarico"
        self.create_header_back(title, self.show_assignments_list, None)

        form = ttk.Frame(self.main_frame)
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(form, text="Cliente *:", width=25, anchor="w").grid(row=0, column=0, pady=5, sticky="w")
        self.assign_vars = {}
        self.assign_vars["client"] = ttk.Combobox(form, state="readonly")
        self.assign_vars["client"].grid(row=0, column=1, pady=5, sticky="ew")
        
        clients = db.get_clients(self.user_id)
        client_map = {c['id']: c['ragione_sociale'] for c in clients}
        self.assign_vars["client"]['values'] = list(client_map.values())
        self.assign_vars["client_map"] = {v: k for k, v in client_map.items()}

        fields = [
            ("Descrizione Progetto *:", "progetto"),
            ("Data Inizio (YYYY-MM-DD) *:", "data_inizio"),
            ("Rif. Determina:", "rif_det"),
            ("Data Determina:", "data_det"),
            ("Nome RUP:", "rup"),
            ("Email RUP:", "email_rup"),
            ("CIG:", "cig"),
        ]

        for idx, (lbl, key) in enumerate(fields, start=1):
            ttk.Label(form, text=lbl, width=25, anchor="w").grid(row=idx, column=0, pady=5, sticky="w")
            e = ttk.Entry(form)
            e.grid(row=idx, column=1, pady=5, sticky="ew")
            self.assign_vars[key] = e

        ttk.Label(form, text="Stato *:", width=25, anchor="w").grid(row=len(fields)+1, column=0, pady=5, sticky="w")
        self.assign_vars["stato"] = ttk.Combobox(form, values=["Attivo", "Completato", "Sospeso"], state="readonly")
        self.assign_vars["stato"].grid(row=len(fields)+1, column=1, pady=5, sticky="ew")
        self.assign_vars["stato"].current(0)

        form.columnconfigure(1, weight=1)

        if existing:
            self.assign_vars["client"].set(client_map.get(existing['client_id'], ""))
            self.assign_vars["progetto"].insert(0, existing['descrizione_progetto'] or "")
            self.assign_vars["data_inizio"].insert(0, existing['data_inizio'] or "")
            self.assign_vars["rif_det"].insert(0, existing['rif_determina_incarico'] or "")
            self.assign_vars["data_det"].insert(0, existing['data_determina'] or "")
            self.assign_vars["rup"].insert(0, existing['nome_rup'] or "")
            self.assign_vars["email_rup"].insert(0, existing['email_rup'] or "")
            self.assign_vars["cig"].insert(0, existing['cig'] or "")
            self.assign_vars["stato"].set(existing['stato'] or "Attivo")

        def save():
            if not all([self.assign_vars["client"].get(), self.assign_vars["progetto"].get(), self.assign_vars["data_inizio"].get()]):
                messagebox.showerror("Errore", "Compila i campi obbligatori")
                return
            try:
                client_id = self.assign_vars["client_map"][self.assign_vars["client"].get()]
                db.save_assignment(self.user_id, assign_id, client_id,
                    self.assign_vars["progetto"].get(),
                    self.assign_vars["data_inizio"].get(),
                    self.assign_vars["rif_det"].get(),
                    self.assign_vars["data_det"].get(),
                    self.assign_vars["rup"].get(),
                    self.assign_vars["email_rup"].get(),
                    self.assign_vars["cig"].get(),
                    self.assign_vars["stato"].get())
                messagebox.showinfo("OK", "Incarico salvato")
                self.show_assignments_list()
            except Exception as e:
                messagebox.showerror("Errore", str(e))

        self.create_save_cancel_btns(lambda _: save(), self.show_assignments_list, None)

    # =========================================================================
    # SEZIONE 6: NUOVA RICEVUTA
    # =========================================================================
    def show_receipt_form(self, _=None):
        self.clear_frame()
        self.create_header_back("Nuova Ricevuta", self.show_receipts_history, None)

        left = ttk.Frame(self.main_frame)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,10))

        right = ttk.Frame(self.main_frame)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10,10))

        # --- FORM SINISTRO ---
        ttk.Label(left, text="Seleziona Incarico:", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0,5))
        self.rec_assign = ttk.Combobox(left, state="readonly")
        self.rec_assign.pack(fill=tk.X, pady=(0,10))

        assignments = db.get_assignments(self.user_id)
        assign_map = {a['id']: f"{a['ragione_sociale']} - {a['descrizione_progetto']}" for a in assignments}
        self.rec_assign['values'] = list(assign_map.values())
        self.rec_assign_map = {v: k for k, v in assign_map.items()}

        ttk.Label(left, text="Anno Riferimento:", font=("Arial", 11, "bold")).pack(anchor="w", pady=(10,5))
        self.rec_year = ttk.Entry(left)
        self.rec_year.insert(0, str(date.today().year))
        self.rec_year.pack(fill=tk.X, pady=(0,10))

        ttk.Label(left, text="Data Emissione (YYYY-MM-DD):", font=("Arial", 11, "bold")).pack(anchor="w", pady=(10,5))
        self.rec_date = ttk.Entry(left)
        self.rec_date.insert(0, date.today().strftime("%Y-%m-%d"))
        self.rec_date.pack(fill=tk.X, pady=(0,10))

        ttk.Label(left, text="Descrizione Prestazione:", font=("Arial", 11, "bold")).pack(anchor="w", pady=(10,5))
        self.rec_desc = tk.Text(left, height=4)
        self.rec_desc.pack(fill=tk.X, pady=(0,10))

        ttk.Label(left, text="Compenso Lordo (€):", font=("Arial", 11, "bold")).pack(anchor="w", pady=(10,5))
        self.rec_lordo = ttk.Entry(left)
        self.rec_lordo.pack(fill=tk.X, pady=(0,10))

        ttk.Label(left, text="Rimborsi Spese Esenti (€):", font=("Arial", 11, "bold")).pack(anchor="w", pady=(10,5))
        self.rec_spese = ttk.Entry(left)
        self.rec_spese.insert(0, "0.00")
        self.rec_spese.pack(fill=tk.X, pady=(0,10))

        ttk.Label(left, text="% Ritenuta IRPEF:", font=("Arial", 11, "bold")).pack(anchor="w", pady=(10,5))
        self.rec_irpef_perc = ttk.Combobox(left, values=["0", "20"], state="readonly")
        self.rec_irpef_perc.current(1)
        self.rec_irpef_perc.pack(fill=tk.X, pady=(0,15))

        ttk.Button(left, text="🧮 Ricalcola", style="Green.TButton", command=self.calculate_receipt).pack(fill=tk.X, pady=10)

        # --- RIEPILOGO DESTRO ---
        ttk.Label(right, text="Riepilogo Calcolo", font=("Arial", 12, "bold")).pack(pady=(0,10))
        self.res_lordo = self.create_res_row(right, "Compenso Lordo:")
        self.res_spese = self.create_res_row(right, "Rimborso Spese:")
        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, pady=5)
        self.res_imp_inps = self.create_res_row(right, "Imponibile INPS:", 10)
        self.res_rit_inps = self.create_res_row(right, "Ritenuta INPS Tot:", 10)
        self.res_quota_inps = self.create_res_row(right, "Quota INPS Utente:", 10, True, "red")
        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, pady=5)
        self.res_irpef = self.create_res_row(right, "Ritenuta IRPEF:", 10, True, "red")
        self.res_bollo = self.create_res_row(right, "Imposta Bollo:", 10)
        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, pady=10)
        self.res_netto = self.create_res_row(right, "NETTO A PAGARE:", 13, True, "green")

        ttk.Button(right, text="💾 Salva e Genera PDF", style="Big.TButton", command=self.save_receipt).pack(pady=20, fill=tk.X)

    def calculate_receipt(self):
        try:
            lordo = float(self.rec_lordo.get() or 0)
            spese = float(self.rec_spese.get() or 0)
            irpef_perc = float(self.rec_irpef_perc.get())
            anno = int(self.rec_year.get())

            cfg = db.get_fiscal_config(self.user_id, anno)
            if not cfg:
                messagebox.showerror("Errore", "Configurazione fiscale non trovata per l'anno")
                return

            # CALCOLO CORRETTO DELL'IMPONIBILE INPS (gestione dello "scavalco")
            cumul = db.get_annual_gross(self.user_id, anno)  # Cumulato prima di questa ricevuta
            soglia = cfg['soglia_inps_no_tax']
            
            if cumul >= soglia:
                # Caso 1: già oltre la franchigia -> tutto il nuovo compenso è imponibile
                imponibile_inps = lordo
            elif cumul + lordo <= soglia:
                # Caso 2: non si raggiunge la franchigia -> niente è imponibile
                imponibile_inps = 0.0
            else:
                # Caso 3: "scavalco" -> solo la parte che supera la franchigia è imponibile
                imponibile_inps = (cumul + lordo) - soglia
            
            rit_inps_tot = imponibile_inps * (cfg['aliquota_gestione_separata'] / 100)
            quota_inps = rit_inps_tot * cfg['quota_carico_utente']
            imp_irpef = lordo * (irpef_perc / 100)
            val_bollo = cfg['valore_bollo'] if lordo >= cfg['soglia_bollo'] else 0.00

            netto = lordo + spese + val_bollo - quota_inps - imp_irpef

            self.current_calc = {
                'lordo': lordo, 'spese': spese, 'imp_inps': imponibile_inps,
                'aliq_inps': cfg['aliquota_gestione_separata'], 'rit_inps': rit_inps_tot,
                'quota_inps': quota_inps, 'aliq_irpef': irpef_perc, 'imp_irpef': imp_irpef,
                'bollo_bool': val_bollo > 0, 'val_bollo': val_bollo, 'netto': netto, 'anno': anno
            }

            self.res_lordo.config(text=f"€ {lordo:.2f}")
            self.res_spese.config(text=f"€ {spese:.2f}")
            self.res_imp_inps.config(text=f"€ {imponibile_inps:.2f}")
            self.res_rit_inps.config(text=f"€ {rit_inps_tot:.2f}")
            self.res_quota_inps.config(text=f"€ -{quota_inps:.2f}")
            self.res_irpef.config(text=f"€ -{imp_irpef:.2f}")
            self.res_bollo.config(text=f"€ {val_bollo:.2f}")
            self.res_netto.config(text=f"€ {netto:.2f}")

        except ValueError:
            messagebox.showerror("Errore", "Valori numerici non validi")

    def save_receipt(self):
        if not self.current_calc:
            messagebox.showwarning("Attenzione", "Calcola prima la ricevuta")
            return
        if not self.rec_assign.get():
            messagebox.showerror("Errore", "Seleziona un incarico")
            return

        c = self.current_calc
        try:
            assign_id = self.rec_assign_map[self.rec_assign.get()]
            num = db.get_next_receipt_number(self.user_id, c['anno'])
            filename = f"RPO_RICEVUTE/User{self.user_id}_RPO_{c['anno']}_{num}.pdf"
            
            db.save_receipt(self.user_id, assign_id, num, c['anno'], self.rec_date.get(), self.rec_desc.get("1.0", tk.END).strip(),
                c['lordo'], c['imp_inps'], c['aliq_inps'], c['rit_inps'], c['quota_inps'],
                c['aliq_irpef'], c['imp_irpef'], c['spese'], c['bollo_bool'], c['val_bollo'], c['netto'], filename)

            profile = db.get_user_profile(self.user_id)
            assignment = db.get_assignment_by_id(assign_id)
            client = db.get_client_by_id(assignment['client_id'])
            
            pdf_data = c.copy()
            pdf_data['numero'] = num
            pdf_data['data'] = self.rec_date.get()
            pdf_data['desc'] = self.rec_desc.get("1.0", tk.END).strip()
            pdf_data['cig'] = assignment['cig']
            pdf_data['rup'] = assignment['nome_rup']
            pdf_data['rif_det'] = assignment['rif_determina_incarico']
            pdf_data['progetto_macro'] = assignment['descrizione_progetto']

            path = genera_pdf_ricevuta(profile, client, pdf_data, filename)
            messagebox.showinfo("Successo", f"Salvata ricevuta {num}/{c['anno']}")
            self.open_pdf(path)
            self.show_receipts_history()
            
        except Exception as e: 
            messagebox.showerror("Errore", str(e))

    def open_pdf(self, path):
        """Versione blindata: trasforma il percorso in assoluto per evitare WinError 2"""
        try:
            # Forza il percorso a essere assoluto e usa i separatori corretti (\ per Windows)
            full_path = os.path.normpath(os.path.abspath(path))
            
            import platform
            import subprocess

            if platform.system() == 'Darwin':       # macOS
                subprocess.call(('open', full_path))
            elif platform.system() == 'Windows':    # Windows
                os.startfile(full_path)
            else:                                   # Linux
                subprocess.call(('xdg-open', full_path))
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile aprire il file: {e}")

    def create_res_row(self, parent, label, font_size=11, is_bold=False, color="black"):
        fr = ttk.Frame(parent); fr.pack(fill=tk.X, pady=3)
        font_s = ("Arial", font_size, "bold" if is_bold else "normal")
        ttk.Label(fr, text=label, font=font_s).pack(side=tk.LEFT)
        l = ttk.Label(fr, text="€ 0.00", font=font_s, foreground=color); l.pack(side=tk.RIGHT)
        return l

    # =========================================================================
    # SEZIONE 7: STORICO E NOTE CREDITO
    # =========================================================================
    def show_receipts_history(self):
        self.clear_frame()
        self.create_header_back("Storico Ricevute", self.show_receipt_form, "+ Nuova")

        cols = ("num", "data", "cliente", "lordo", "netto")
        tree = ttk.Treeview(self.main_frame, columns=cols, show="headings")
        tree.heading("num", text="N."); tree.column("num", width=60)
        tree.heading("data", text="Data"); tree.column("data", width=100)
        tree.heading("cliente", text="Cliente"); tree.column("cliente", width=250)
        tree.heading("lordo", text="Lordo"); tree.column("lordo", width=120)
        tree.heading("netto", text="Netto a Pagare"); tree.column("netto", width=120)
        tree.pack(fill=tk.BOTH, expand=True, pady=10)

        for r in db.get_receipts(self.user_id):
            num_fmt = f"{r['numero_progressivo']}/{r['anno_riferimento']}"
            tags = ('credit_note',) if r['importo_lordo'] < 0 else ()
            tree.insert("", tk.END, iid=r['id'], values=(
                num_fmt, r['data_emissione'], r['ragione_sociale'], 
                f"€ {r['importo_lordo']:.2f}", f"€ {r['netto_a_pagare']:.2f}"
            ), tags=tags)
        
        tree.tag_configure('credit_note', foreground="red")

        def open_selected_pdf(event=None):
            if not tree.selection(): return
            rel_path = db.get_receipt_path(tree.selection()[0])
            if rel_path:
                full_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path))
                if os.path.exists(full_path):
                    self.open_pdf(full_path)
                else: messagebox.showerror("Err", "File non trovato")

        tree.bind("<Double-1>", open_selected_pdf)

        def create_credit_note():
            if not tree.selection(): return
            orig_id = tree.selection()[0]
            orig_data = db.get_receipt_by_id(orig_id)
            if not orig_data or orig_data['lordo'] < 0: return 
            
            if not messagebox.askyesno("Conferma", "Generare Nota di Credito?"): return
            
            try:
                curr_year = date.today().year
                today_str = date.today().strftime("%Y-%m-%d")
                new_num = db.get_next_receipt_number(self.user_id, curr_year)
                new_desc = f"STORNO TOTALE Ricevuta n. {orig_data['numero']}/{orig_data['anno']} - {orig_data['desc']}"
                
                new_vals = {k: -orig_data[k] for k in ['lordo','spese','imp_irpef','quota_inps','val_bollo','netto','imp_inps','rit_inps']}
                
                fname = f"RPO_RICEVUTE/User{self.user_id}_RPO_{curr_year}_{new_num}_STORNO.pdf"
                
                db.save_receipt(self.user_id, orig_data['assign_id'], new_num, curr_year, today_str, new_desc,
                    new_vals['lordo'], new_vals['imp_inps'], orig_data['aliq_inps'], new_vals['rit_inps'], new_vals['quota_inps'],
                    orig_data['aliq_irpef'], new_vals['imp_irpef'], new_vals['spese'], orig_data['bollo_bool'], new_vals['val_bollo'], new_vals['netto'], fname)
                
                prof = db.get_user_profile(self.user_id)
                ass = db.get_assignment_by_id(orig_data['assign_id'])
                cli = db.get_client_by_id(ass['client_id'])
                
                pdf_d = {'numero': new_num, 'anno': curr_year, 'data': today_str, 'desc': new_desc, 
                         'lordo': new_vals['lordo'], 'spese': new_vals['spese'], 'imp_irpef': new_vals['imp_irpef'], 
                         'aliq_irpef': orig_data['aliq_irpef'], 'quota_inps': new_vals['quota_inps'], 'val_bollo': new_vals['val_bollo'], 
                         'netto': new_vals['netto'], 'cig': ass['cig'], 'rup': ass['nome_rup'], 'rif_det': ass['rif_determina_incarico'], 
                         'imp_inps': new_vals['imp_inps'], 'rit_inps': new_vals['rit_inps'],
                         'progetto_macro': ass['descrizione_progetto']}
                
                genera_pdf_ricevuta(prof, cli, pdf_d, fname, is_credit_note=True)
                self.show_receipts_history()
            except Exception as e: 
                messagebox.showerror("Err", str(e))

        def do_del():
            if not tree.selection(): return
            rid = tree.selection()[0]
            data = db.get_receipt_by_id(rid)
            if messagebox.askyesno("Elimina", "Cancellare definitivamente record e file PDF?"):
                if data['filename']:
                    fpath = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), data['filename']))
                    if os.path.exists(fpath): 
                        os.remove(fpath)
                
                conn = db._get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM receipts WHERE id=?", (rid,))
                conn.commit()
                conn.close()
                self.show_receipts_history()

        bx = ttk.Frame(self.main_frame, padding=10)
        bx.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        ttk.Button(bx, text="📄 Apri PDF", style="Big.TButton", command=open_selected_pdf).pack(side=tk.LEFT, padx=10)
        ttk.Button(bx, text="↩ Storna Rpo (Genera Nota di Credito)", style="Red.TButton", command=create_credit_note).pack(side=tk.LEFT, padx=10)
        ttk.Button(bx, text="🗑 Elimina", command=do_del).pack(side=tk.RIGHT, padx=10)

    # Helpers
    def create_header_back(self, title, add_command, btn_text="+ Aggiungi"):
        h = ttk.Frame(self.main_frame)
        h.pack(fill=tk.X, pady=(0,15))
        ttk.Button(h, text="⬅ Home", command=lambda: self.check_start()).pack(side=tk.LEFT)
        ttk.Label(h, text=title, font=("Arial", 16, "bold")).pack(side=tk.LEFT, padx=20)
        if btn_text: 
            # Sostituisci la riga 1565 con questa versione più "pulita":
            ttk.Button(h, text=btn_text, 
                    command=lambda: add_command(None) if add_command != self.show_dashboard else self.show_receipt_form(), 
                    style="Big.TButton").pack(side=tk.RIGHT)
            
    def create_crud_buttons(self, tree, edit_cmd, delete_cmd, reload_cmd):
        bx = ttk.Frame(self.main_frame)
        bx.pack(pady=10)
        ttk.Button(bx, text="✎ Modifica", command=lambda: edit_cmd(tree.selection()[0]) if tree.selection() else None).pack(side=tk.LEFT, padx=5)
        def do_del():
            if not tree.selection(): return
            if messagebox.askyesno("Conferma", "Eliminare elemento?"): 
                delete_cmd(tree.selection()[0])
                reload_cmd()
        ttk.Button(bx, text="🗑 Elimina", command=do_del).pack(side=tk.LEFT, padx=5)

    def create_save_cancel_btns(self, save_cmd, cancel_cmd, obj_id):
        bx = ttk.Frame(self.main_frame)
        bx.pack(pady=20)
        ttk.Button(bx, text="Salva", style="Big.TButton", command=lambda: save_cmd(obj_id)).pack(side=tk.LEFT, padx=10)
        ttk.Button(bx, text="Annulla", command=cancel_cmd).pack(side=tk.LEFT, padx=10)


# =========================================================================
# AVVIO APPLICAZIONE
# =========================================================================
if __name__ == "__main__":
    root = tk.Tk()
    
    # Callback che viene chiamata se il login ha successo
    def launch_app(user_id, user_name):
        app = GestionaleRicevuteApp(root, user_id, user_name)

    # Avvia la schermata di login invece dell'app diretta
    login_screen = LoginWindow(root, on_login_success=launch_app)
    
    root.mainloop()
