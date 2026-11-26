from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    """
    Storage privado para arquivos PDF do acervo.

    Os arquivos ficam fora de MEDIA_ROOT e nunca possuem URL pública direta;
    a entrega ocorre exclusivamente via FileResponse nos endpoints /ler/ e /download/.
    """

    def __init__(self, location=None, **kwargs):
        super().__init__(
            location=location or settings.PRIVATE_MEDIA_ROOT,
            base_url=None,
            **kwargs,
        )

    def url(self, name):
        raise ValueError(
            'Arquivos armazenados em PrivateMediaStorage não possuem URL pública direta.'
        )


private_storage = PrivateMediaStorage()
