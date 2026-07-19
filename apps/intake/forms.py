"""Forms para o app intake."""

from django import forms


class CaseUploadForm(forms.Form):
    """Formulário de upload de PDFs de encaminhamento.

    A validação e processamento dos arquivos é feita via
    ``services.process_uploaded_files`` usando ``request.FILES.getlist()``
    diretamente, já que o ``FileField`` do Django não suporta seleção
    múltipla de arquivos de forma nativa.
    """

    pass
