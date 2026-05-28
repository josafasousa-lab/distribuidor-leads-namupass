from pydantic import BaseModel


class Lead(BaseModel):
    row_id: int
    empresa: str
    telefone_raw: str
    telefone: str | None = None
    estado: str
    cidade: str
    endereco: str = ""
    categoria: str
    origem: str
    modalidade: str
    data_importacao: str = ""


class Consultor(BaseModel):
    nome: str
    ac_user_id: int
    ativo: bool = True


class RunReport(BaseModel):
    run_id: str
    dry_run: bool
    total_elegiveis: int
    total_selecionados: int
    total_invalidos: int
    sucessos: list
    falhas: list
    executado: bool
