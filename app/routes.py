import json
from flask import Blueprint, render_template, request, jsonify
from app.hl7_parser import parser, SEGMENT_DESCRIPTIONS, FIELD_DESCRIPTIONS

main_bp = Blueprint("main", __name__)

SAMPLE_MESSAGES = {
    "oru_r01": {
        "label": "ORU^R01 — Referto di laboratorio",
        "message": "MSH|^~\\&|LIS|OSDAL|HIS|OSDAL|20240315143022||ORU^R01|MSG00123|P|2.5\rPID|1||123456^^^OSDAL||Rossi^Mario||19800315|M|||Via Roma 1^^Milano^^20100\rOBR|1||LAB001|GLU^Glucosio|||20240315140000|||||||20240315143000\rOBX|1|NM|GLU^Glucosio|1|5.2|mmol/L|3.5-6.1|N|||F|||20240315143000\rOBX|2|NM|HB^Emoglobina|1|14.5|g/dL|12.0-17.5|N|||F"
    },
    "adt_a01": {
        "label": "ADT^A01 — Ammissione paziente",
        "message": "MSH|^~\\&|ADT|OSPEDALE|HIS|OSPEDALE|20240315090000||ADT^A01|MSG00124|P|2.5\rEVN|A01|20240315090000\rPID|1||789012^^^OSDAL||Bianchi^Anna||19650822|F|||Via Verdi 5^^Roma^^00100\rPV1|1|I|CARD^101^A|||DR_VERDI^Verdi^Luca^^^Dr."
    },
    "orm_o01": {
        "label": "ORM^O01 — Ordine esame",
        "message": "MSH|^~\\&|OE|OSDAL|LIS|OSDAL|20240315160000||ORM^O01|MSG00127|P|2.5\rPID|1||567890^^^OSDAL||Ferrari^Roberto||19551230|M\rORC|NW|ORD001|||CM||||20240315160000\rOBR|1|ORD001||EMOCROMO^Emocromo completo|||20240315160000"
    },
    "adt_a08": {
        "label": "ADT^A08 — Aggiornamento dati paziente",
        "message": "MSH|^~\\&|ADT|OSPEDALE|HIS|OSPEDALE|20240315120000||ADT^A08|MSG00130|P|2.5\rEVN|A08|20240315120000\rPID|1||345678^^^OSDAL||Conti^Marco^^Dr.||19720510|M|||Via Manzoni 10^^Torino\rPV1|1|O|AMBU^01^B"
    },
    "ack": {
        "label": "ACK — Acknowledgment",
        "message": "MSH|^~\\&|HIS|OSDAL|LIS|OSDAL|20240315143100||ACK^R01|MSG00200|P|2.5\rMSA|AA|MSG00123|Messaggio ricevuto correttamente"
    },
    "error_example": {
        "label": "⚠️ Esempio con errori (PID mancante)",
        "message": "MSH|^~\\&|LIS|OSDAL|HIS|OSDAL|20240315||ORU^R01|MSG005|P|2.5\rOBR|1||LAB002|HB^Emoglobina\rOBX|1|NM|HB|1|14.5|g/dL|||N|||F"
    },
}


@main_bp.route("/")
def index():
    return render_template("index.html", samples=SAMPLE_MESSAGES)


@main_bp.route("/validate", methods=["POST"])
def validate():
    data = request.get_json(silent=True) or {}
    raw = data.get("message", "").strip()
    if not raw:
        return jsonify({"error": "Nessun messaggio fornito"}), 400

    result = parser.parse(raw)
    out = result.to_dict()

    # Add human-readable segment info
    out["segment_details"] = []
    for seg in result.segment_list:
        fd = FIELD_DESCRIPTIONS.get(seg.name, {})
        fields_info = []
        for i, val in enumerate(seg.fields, start=1):
            if val:
                fields_info.append({
                    "position": i,
                    "label": fd.get(i, f"Campo {i}"),
                    "value": val,
                })
        out["segment_details"].append({
            "name": seg.name,
            "description": SEGMENT_DESCRIPTIONS.get(seg.name, "Segmento HL7"),
            "raw": seg.raw,
            "fields": fields_info,
        })

    return jsonify(out)


@main_bp.route("/samples")
def samples():
    return jsonify(SAMPLE_MESSAGES)
