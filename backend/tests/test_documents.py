import io
import pytest
from fastapi import HTTPException
from pypdf import PdfWriter
from app.documents import detect_file, extract


def test_utf8_extraction():
    raw='Chứng nhận an toàn đồ chơi LEGO. Chi nhánh Đông.'.encode()
    assert detect_file('chung-nhan.txt',raw)=='text/plain'
    text,status=extract(raw,'text/plain')
    assert 'an toàn' in text and status=='ready'


def test_scan_and_image_do_not_claim_ocr():
    out=io.BytesIO()
    writer=PdfWriter()
    writer.add_blank_page(width=100,height=100)
    writer.write(out)
    assert extract(out.getvalue(),'application/pdf')==('','needs_ocr')
    assert extract(b'image','image/png')==('','needs_ocr')


@pytest.mark.parametrize('name,body',[('fake.pdf',b'<html>bad</html>'),('file.exe',b'MZ...'),('bad.txt',b'\xff'),('empty.txt',b''),('big.txt',b'x'*(10*1024*1024+1))],ids=['wrong-signature','executable','invalid-utf8','empty','over-limit'])
def test_reject_invalid_files(name,body):
    with pytest.raises(HTTPException):
        detect_file(name,body)
