"""
HL7 v2.x Parser & Validator — standalone, zero external deps.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

REQUIRED_SEGMENTS = {
    "ADT": ["MSH", "EVN", "PID", "PV1"],
    "ORM": ["MSH", "PID", "ORC", "OBR"],
    "ORU": ["MSH", "PID", "OBR", "OBX"],
    "MDM": ["MSH", "EVN", "PID", "TXA"],
    "SIU": ["MSH", "SCH", "PID"],
    "MFN": ["MSH", "MFI", "MFE"],
    "BAR": ["MSH", "EVN", "PID", "PV1"],
    "DFT": ["MSH", "EVN", "PID", "PV1", "FT1"],
}

VALID_HL7_VERSIONS = {"2.1","2.2","2.3","2.3.1","2.4","2.5","2.5.1","2.6","2.7","2.8"}
VALID_MESSAGE_TYPES = {
    "ADT","ORM","ORU","MDM","SIU","MFN","BAR","DFT",
    "ACK","QRY","DSR","NMQ","NMR","PPR","RAS","RDS","RGV",
}
VALID_SEX = {"M", "F", "O", "U", "A", "N", "C"}

SEGMENT_DESCRIPTIONS = {
    "MSH": "Message Header",
    "PID": "Patient Identification",
    "PV1": "Patient Visit",
    "EVN": "Event Type",
    "OBR": "Observation Request",
    "OBX": "Observation Result",
    "ORC": "Common Order",
    "NTE": "Notes and Comments",
    "AL1": "Allergy Information",
    "DG1": "Diagnosis",
    "GT1": "Guarantor",
    "IN1": "Insurance",
    "MSA": "Message Acknowledgment",
    "ERR": "Error",
    "SCH": "Scheduling Activity",
    "TXA": "Transcription Document Header",
    "MFI": "Master File Identification",
    "MFE": "Master File Entry",
    "FT1": "Financial Transaction",
    "PR1": "Procedures",
    "SPM": "Specimen",
    "SAC": "Specimen Container",
    "TQ1": "Timing/Quantity",
    "RXA": "Pharmacy Administration",
    "RXR": "Pharmacy Route",
}

FIELD_DESCRIPTIONS = {
    "MSH": {
        1: "Field Separator", 2: "Encoding Characters", 3: "Sending Application",
        4: "Sending Facility", 5: "Receiving Application", 6: "Receiving Facility",
        7: "Date/Time of Message", 8: "Security", 9: "Message Type",
        10: "Message Control ID", 11: "Processing ID", 12: "Version ID",
        13: "Sequence Number", 14: "Continuation Pointer", 15: "Accept Acknowledgment Type",
        16: "Application Acknowledgment Type", 17: "Country Code",
    },
    "PID": {
        1: "Set ID", 2: "Patient ID (external)", 3: "Patient Identifier List",
        4: "Alternate Patient ID", 5: "Patient Name", 6: "Mother's Maiden Name",
        7: "Date/Time of Birth", 8: "Administrative Sex", 9: "Patient Alias",
        10: "Race", 11: "Patient Address", 12: "County Code", 13: "Phone Number (Home)",
        14: "Phone Number (Business)", 15: "Primary Language", 16: "Marital Status",
        18: "Patient Account Number", 19: "SSN Number", 22: "Ethnic Group",
        29: "Patient Death Date and Time", 30: "Patient Death Indicator",
    },
    "PV1": {
        1: "Set ID", 2: "Patient Class", 3: "Assigned Patient Location",
        4: "Admission Type", 7: "Attending Doctor", 8: "Referring Doctor",
        9: "Consulting Doctor", 10: "Hospital Service", 17: "Admitting Doctor",
        19: "Visit Number", 44: "Admit Date/Time", 45: "Discharge Date/Time",
    },
    "OBR": {
        1: "Set ID", 2: "Placer Order Number", 3: "Filler Order Number",
        4: "Universal Service Identifier", 5: "Priority", 6: "Requested Date/Time",
        7: "Observation Date/Time", 14: "Specimen Received Date/Time",
        22: "Results Report/Status Change Date/Time", 24: "Diagnostic Serv Sect ID",
        25: "Result Status", 27: "Quantity/Timing",
    },
    "OBX": {
        1: "Set ID", 2: "Value Type", 3: "Observation Identifier",
        4: "Observation Sub-ID", 5: "Observation Value", 6: "Units",
        7: "References Range", 8: "Abnormal Flags", 11: "Observation Result Status",
        14: "Date/Time of Observation",
    },
    "EVN": {
        1: "Event Type Code", 2: "Recorded Date/Time", 3: "Date/Time Planned Event",
        4: "Event Reason Code", 5: "Operator ID",
    },
}


@dataclass
class ParsedSegment:
    name: str
    fields: list
    raw: str
    index: int  # position in message (0-based)

    def get(self, position: int) -> str:
        try:
            return self.fields[position - 1] or ""
        except IndexError:
            return ""

    def component(self, position: int, comp: int) -> str:
        val = self.get(position)
        parts = val.split("^")
        try:
            return parts[comp - 1]
        except IndexError:
            return ""


@dataclass
class Issue:
    severity: str       # ERROR | WARNING | INFO
    segment: str
    field_pos: str
    code: str
    description: str
    suggestion: str = ""


@dataclass
class HL7ParseResult:
    raw: str
    is_valid: bool = False
    segments: dict = field(default_factory=dict)
    segment_list: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    # Extracted key fields
    message_type: Optional[str] = None
    event_type: Optional[str] = None
    hl7_version: Optional[str] = None
    message_id: Optional[str] = None
    sending_app: Optional[str] = None
    sending_facility: Optional[str] = None
    receiving_app: Optional[str] = None
    receiving_facility: Optional[str] = None
    message_datetime: Optional[str] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    dob: Optional[str] = None
    sex: Optional[str] = None

    @property
    def errors(self): return [i for i in self.issues if i.severity == "ERROR"]
    @property
    def warnings(self): return [i for i in self.issues if i.severity == "WARNING"]
    @property
    def infos(self): return [i for i in self.issues if i.severity == "INFO"]

    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "raw": self.raw,
            "message_type": self.message_type,
            "event_type": self.event_type,
            "hl7_version": self.hl7_version,
            "message_id": self.message_id,
            "sending_app": self.sending_app,
            "sending_facility": self.sending_facility,
            "receiving_app": self.receiving_app,
            "receiving_facility": self.receiving_facility,
            "message_datetime": self.message_datetime,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "dob": self.dob,
            "sex": self.sex,
            "segment_count": len(self.segment_list),
            "segment_names": [s.name for s in self.segment_list],
            "issues": [
                {
                    "severity": i.severity,
                    "segment": i.segment,
                    "field": i.field_pos,
                    "code": i.code,
                    "description": i.description,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "segments": {
                name: [{"raw": s.raw, "fields": s.fields} for s in segs]
                for name, segs in self.segments.items()
            },
        }


class HL7Parser:

    def parse(self, raw: str) -> HL7ParseResult:
        raw = self._normalise(raw)
        result = HL7ParseResult(raw=raw)

        if not raw.strip():
            result.issues.append(Issue("ERROR", "—", "—", "E001",
                "Il messaggio è vuoto.", "Inserisci un messaggio HL7 valido."))
            return result

        if not raw.startswith("MSH"):
            result.issues.append(Issue("ERROR", "MSH", "1", "E002",
                "Il messaggio deve iniziare con il segmento MSH.",
                "Verifica che il messaggio sia completo e inizi con 'MSH|'."))
            return result

        if len(raw) < 8 or raw[3] not in "|^":
            result.issues.append(Issue("ERROR", "MSH", "1", "E003",
                "Separatore di campo MSH non valido.",
                "Il quarto carattere di MSH deve essere il separatore '|'."))
            return result

        sep = raw[3]
        lines = [l for l in raw.split("\r") if l.strip()]

        for idx, line in enumerate(lines):
            name = line[:3]
            if name == "MSH":
                fields = [sep] + line[4:].split(sep)
            else:
                fields = line.split(sep)[1:]
            seg = ParsedSegment(name=name, fields=fields, raw=line, index=idx)
            result.segment_list.append(seg)
            result.segments.setdefault(name, []).append(seg)

        msh = result.segments.get("MSH", [None])[0]
        if msh:
            self._extract_msh(msh, result)

        pid_list = result.segments.get("PID", [])
        if pid_list:
            self._extract_pid(pid_list[0], result)

        # Run all validators
        self._val_msh(result)
        self._val_required_segments(result)
        self._val_pid(result)
        self._val_obx(result)
        self._val_evn(result)
        self._check_duplicate_segments(result)
        self._check_segment_order(result)

        result.is_valid = len(result.errors) == 0
        return result

    # ── Extraction ─────────────────────────────────────────────────
    def _normalise(self, raw: str) -> str:
        return raw.strip().replace("\r\n", "\r").replace("\n", "\r")

    def _extract_msh(self, msh: ParsedSegment, r: HL7ParseResult):
        msg_type_raw = msh.get(9)
        if "^" in msg_type_raw:
            parts = msg_type_raw.split("^")
            r.message_type = parts[0] or None
            r.event_type = parts[1] if len(parts) > 1 else None
        else:
            r.message_type = msg_type_raw or None
        r.hl7_version = msh.get(12) or None
        r.message_id = msh.get(10) or None
        r.sending_app = msh.get(3) or None
        r.sending_facility = msh.get(4) or None
        r.receiving_app = msh.get(5) or None
        r.receiving_facility = msh.get(6) or None
        r.message_datetime = msh.get(7) or None

    def _extract_pid(self, pid: ParsedSegment, r: HL7ParseResult):
        cx = pid.get(3)
        r.patient_id = cx.split("^")[0] if cx else (pid.get(2) or None)
        name_raw = pid.get(5)
        if name_raw:
            parts = name_raw.split("^")
            last = parts[0] if parts else ""
            first = parts[1] if len(parts) > 1 else ""
            r.patient_name = f"{last} {first}".strip() or None
        r.dob = pid.get(7) or None
        r.sex = pid.get(8) or None

    # ── Validators ─────────────────────────────────────────────────
    def _val_msh(self, r: HL7ParseResult):
        msh = r.segments.get("MSH", [None])[0]
        if not msh:
            return

        if not r.message_type:
            r.issues.append(Issue("ERROR", "MSH", "9", "E010",
                "Tipo messaggio (MSH-9) mancante o vuoto.",
                "Inserire il tipo messaggio es. 'ORU^R01' o 'ADT^A01'."))
        elif r.message_type not in VALID_MESSAGE_TYPES:
            r.issues.append(Issue("WARNING", "MSH", "9", "W010",
                f"Tipo messaggio '{r.message_type}' non è un tipo HL7 standard.",
                f"Tipi validi: {', '.join(sorted(VALID_MESSAGE_TYPES))}."))

        if not r.hl7_version:
            r.issues.append(Issue("ERROR", "MSH", "12", "E011",
                "Versione HL7 (MSH-12) mancante.",
                "Inserire la versione HL7 es. '2.5' o '2.5.1'."))
        elif r.hl7_version not in VALID_HL7_VERSIONS:
            r.issues.append(Issue("WARNING", "MSH", "12", "W011",
                f"Versione HL7 '{r.hl7_version}' non riconosciuta.",
                f"Versioni supportate: {', '.join(sorted(VALID_HL7_VERSIONS))}."))

        if not r.message_id:
            r.issues.append(Issue("ERROR", "MSH", "10", "E012",
                "Message Control ID (MSH-10) mancante.",
                "MSH-10 deve contenere un identificatore univoco del messaggio."))

        if not r.sending_facility:
            r.issues.append(Issue("WARNING", "MSH", "4", "W013",
                "Sending Facility (MSH-4) mancante.",
                "Indicare il sistema/facility mittente."))

        if not r.receiving_facility:
            r.issues.append(Issue("WARNING", "MSH", "6", "W014",
                "Receiving Facility (MSH-6) mancante.",
                "Indicare il sistema/facility destinatario."))

        dt = r.message_datetime
        if not dt:
            r.issues.append(Issue("WARNING", "MSH", "7", "W015",
                "Data/ora messaggio (MSH-7) mancante.",
                "Formato atteso: YYYYMMDDHHMMSS (es. 20240315143022)."))
        elif not self._valid_hl7_dt(dt):
            r.issues.append(Issue("WARNING", "MSH", "7", "W016",
                f"Data/ora '{dt}' non valida.",
                "Formato atteso: YYYYMMDDHHMMSS o YYYYMMDD."))

        enc = msh.get(2)
        if enc and enc not in {"^~\\&", "^~\\&#", "^~\\&Z"}:
            r.issues.append(Issue("INFO", "MSH", "2", "I010",
                f"Encoding characters '{enc}' non standard.",
                "Il valore standard è '^~\\&'."))

    def _val_required_segments(self, r: HL7ParseResult):
        if not r.message_type:
            return
        required = REQUIRED_SEGMENTS.get(r.message_type, ["MSH"])
        for seg in required:
            if seg not in r.segments:
                r.issues.append(Issue("ERROR", seg, "—", "E020",
                    f"Segmento obbligatorio '{seg}' mancante per messaggi {r.message_type}.",
                    f"Aggiungere il segmento {seg} ({SEGMENT_DESCRIPTIONS.get(seg, '')})."))

    def _val_pid(self, r: HL7ParseResult):
        pid_list = r.segments.get("PID", [])
        if not pid_list:
            return
        pid = pid_list[0]

        if not r.patient_id:
            r.issues.append(Issue("ERROR", "PID", "3", "E030",
                "Patient ID (PID-3) mancante.",
                "PID-3 deve contenere almeno un identificatore paziente."))

        if not pid.get(5):
            r.issues.append(Issue("WARNING", "PID", "5", "W031",
                "Nome paziente (PID-5) mancante.",
                "Formato: COGNOME^NOME^SECONDO_NOME^SUFFISSO^PREFISSO."))

        dob = r.dob
        if dob:
            if not self._valid_hl7_date(dob):
                r.issues.append(Issue("WARNING", "PID", "7", "W032",
                    f"Data di nascita '{dob}' non valida.",
                    "Formato atteso: YYYYMMDD (es. 19800315)."))
            else:
                # Check it's not in the future
                try:
                    dt = datetime.strptime(dob[:8], "%Y%m%d")
                    if dt > datetime.now():
                        r.issues.append(Issue("WARNING", "PID", "7", "W033",
                            "La data di nascita è nel futuro.",
                            "Verificare che la data sia corretta."))
                except ValueError:
                    pass

        sex = r.sex
        if sex and sex not in VALID_SEX:
            r.issues.append(Issue("WARNING", "PID", "8", "W034",
                f"Sesso '{sex}' non è un valore HL7 valido.",
                f"Valori ammessi: {', '.join(sorted(VALID_SEX))}."))

    def _val_obx(self, r: HL7ParseResult):
        for obx in r.segments.get("OBX", []):
            val_type = obx.get(2)
            valid_types = {"NM","ST","TX","FT","CWE","CE","CX","SI","DT","TM","DTM","ED","RP","SN","ID","IS","NR"}
            if val_type and val_type not in valid_types:
                r.issues.append(Issue("INFO", "OBX", "2", "I020",
                    f"OBX-2 value type '{val_type}' non standard.",
                    f"Tipi comuni: NM (numeric), ST (string), TX (text), CWE (coded), CE."))
            result_status = obx.get(11)
            valid_status = {"C","D","F","I","N","O","P","R","S","U","W","X"}
            if result_status and result_status not in valid_status:
                r.issues.append(Issue("WARNING", "OBX", "11", "W040",
                    f"OBX-11 result status '{result_status}' non valido.",
                    f"Valori validi: F (final), P (preliminary), C (correction), R (results entered)."))

    def _val_evn(self, r: HL7ParseResult):
        for evn in r.segments.get("EVN", []):
            recorded = evn.get(2)
            if not recorded:
                r.issues.append(Issue("WARNING", "EVN", "2", "W050",
                    "EVN-2 (Recorded Date/Time) mancante.",
                    "Inserire la data/ora di registrazione dell'evento."))

    def _check_duplicate_segments(self, r: HL7ParseResult):
        non_repeatable = {"MSH", "EVN", "PV1"}
        for seg_name in non_repeatable:
            if len(r.segments.get(seg_name, [])) > 1:
                r.issues.append(Issue("WARNING", seg_name, "—", "W060",
                    f"Segmento {seg_name} presente più volte nel messaggio.",
                    f"{seg_name} non dovrebbe essere ripetuto."))

    def _check_segment_order(self, r: HL7ParseResult):
        names = [s.name for s in r.segment_list]
        if names and names[0] != "MSH":
            r.issues.append(Issue("ERROR", names[0], "—", "E060",
                f"Il primo segmento è '{names[0]}', deve essere MSH.",
                "MSH deve sempre essere il primo segmento del messaggio."))

        # MSA must come after MSH
        if "MSA" in names and "MSH" in names:
            if names.index("MSA") < names.index("MSH"):
                r.issues.append(Issue("ERROR", "MSA", "—", "E061",
                    "MSA appare prima di MSH.", "MSA deve seguire MSH."))

    # ── Helpers ─────────────────────────────────────────────────────
    def _valid_hl7_dt(self, s: str) -> bool:
        clean = re.sub(r"[+-]\d{4}$", "", s.strip())
        for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"):
            try:
                datetime.strptime(clean[:len(fmt.replace("%Y","XXXX").replace("%m","XX").replace("%d","XX").replace("%H","XX").replace("%M","XX").replace("%S","XX"))], fmt)
                return True
            except ValueError:
                continue
        return False

    def _valid_hl7_date(self, s: str) -> bool:
        try:
            datetime.strptime(s[:8], "%Y%m%d")
            return True
        except ValueError:
            return False


parser = HL7Parser()
