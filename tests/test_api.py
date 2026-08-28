import os
import tempfile
import unittest

os.environ["AGIPROZ_SECRET_KEY"] = "teste-agiproz"

import app as agiproz


class AgiProzAPITest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_instance = agiproz.INSTANCE_DIR
        self.old_db = agiproz.DB_PATH
        agiproz.INSTANCE_DIR = agiproz.Path(self.tempdir.name)
        agiproz.DB_PATH = agiproz.INSTANCE_DIR / "test.sqlite3"
        agiproz.init_db()
        self.client = agiproz.app.test_client()

    def tearDown(self):
        agiproz.INSTANCE_DIR = self.old_instance
        agiproz.DB_PATH = self.old_db
        self.tempdir.cleanup()

    def login_admin(self):
        response = self.client.post("/api/setup", json={
            "name": "Administrador",
            "email": "admin@agiproz.local",
            "password": "AgiProz@2026",
        })
        self.assertEqual(response.status_code, 200)
        return response

    def create_client(self):
        response = self.client.post("/api/clients", json={
            "name": "Cliente Teste",
            "cpf": "52998224725",
            "email": "cliente.teste@example.com",
            "phone": "31999998888",
            "address": "Rua de Teste, 100",
            "whatsappConfirmed": True,
        })
        self.assertEqual(response.status_code, 201)
        return response.json["client"]["id"]

    def test_primeiro_acesso(self):
        response = self.client.get("/api/bootstrap")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["setupRequired"])

    def test_segundo_admin_e_rejeitado(self):
        self.login_admin()
        self.client.post("/api/logout")
        response = self.client.post("/api/setup", json={
            "name": "Segundo Administrador",
            "email": "admin2@agiproz.local",
            "password": "AgiProz@2026",
        })
        self.assertEqual(response.status_code, 409)

    def test_operador_nao_acessa_auditoria(self):
        self.login_admin()
        response = self.client.post("/api/users", json={
            "name": "Operador Teste",
            "login": "operador.teste",
            "email": "operador@agiproz.local",
        })
        self.assertEqual(response.status_code, 201)
        temporary_password = response.json["temporaryPassword"]
        self.client.post("/api/logout")
        response = self.client.post("/api/login", json={
            "login": "operador.teste",
            "password": temporary_password,
        })
        self.assertEqual(response.status_code, 200)
        response = self.client.post("/api/password/change", json={
            "password": "Operador@2026",
            "password2": "Operador@2026",
        })
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/audit")
        self.assertEqual(response.status_code, 403)

    def test_criacao_de_admin_e_dados(self):
        self.login_admin()
        response = self.client.get("/api/data")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["clients"], [])

    def test_operador_so_pode_ser_criado_por_admin(self):
        self.login_admin()
        response = self.client.post("/api/users", json={
            "name": "Operador Teste",
            "login": "operador.teste",
            "email": "operador@agiproz.local",
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json["temporaryPassword"])


    def test_senha_temporaria_bloqueia_api_ate_troca(self):
        self.login_admin()
        response = self.client.post("/api/users", json={
            "name": "Operador Teste",
            "login": "operador.teste",
            "email": "operador@agiproz.local",
        })
        self.assertEqual(response.status_code, 201)
        temporary_password = response.json["temporaryPassword"]
        self.client.post("/api/logout")

        response = self.client.post("/api/login", json={
            "login": "operador.teste",
            "password": temporary_password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["user"]["forcePasswordChange"])

        response = self.client.get("/api/data")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json["forcePasswordChange"])

        response = self.client.post("/api/password/change", json={
            "password": "Operador@2026",
            "password2": "Operador@2026",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["user"]["forcePasswordChange"])

        response = self.client.get("/api/data")
        self.assertEqual(response.status_code, 200)

    def test_backend_valida_dados_do_operador(self):
        self.login_admin()
        response = self.client.post("/api/users", json={
            "name": "123456",
            "login": "Login Com Espaco",
            "email": "operador@agiproz.local",
        })
        self.assertEqual(response.status_code, 400)

    def test_backend_exige_confirmacao_do_whatsapp(self):
        self.login_admin()
        response = self.client.post("/api/clients", json={
            "name": "Cliente Teste",
            "cpf": "52998224725",
            "email": "cliente.teste@example.com",
            "phone": "31999998888",
            "address": "Rua de Teste, 100",
            "whatsappConfirmed": False,
        })
        self.assertEqual(response.status_code, 400)

    def test_cria_emprestimo_semanal(self):
        self.login_admin()
        client_id = self.create_client()
        response = self.client.post("/api/loans", json={
            "clientId": client_id,
            "amount": 1000,
            "interest": 10,
            "installments": 4,
            "frequency": "weekly",
            "due": "2099-01-05",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["loan"]["frequency"], "weekly")

    def test_pagamento_mantem_datas_fixas(self):
        self.login_admin()
        client_id = self.create_client()
        response = self.client.post("/api/loans", json={
            "clientId": client_id,
            "amount": 1000,
            "interest": 10,
            "installments": 4,
            "frequency": "weekly",
            "due": "2099-01-05",
        })
        loan_id = response.json["loan"]["id"]
        response = self.client.post("/api/payments", json={"loanId": loan_id})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["payment"]["value"], 275.0)
        installments = self.client.get("/api/data").json["installments"]
        self.assertEqual(
            [item["due"] for item in installments],
            ["2099-01-05", "2099-01-12", "2099-01-19", "2099-01-26"],
        )

    def test_data_de_negocio_usa_fuso_de_sao_paulo(self):
        self.assertEqual(agiproz.local_today().tzinfo, None)
        self.assertEqual(agiproz.local_now().tzinfo.key, "America/Sao_Paulo")

    def test_calendario_mensal_preserva_dia_de_referencia(self):
        self.login_admin()
        client_id = self.create_client()
        response = self.client.post("/api/loans", json={
            "clientId": client_id,
            "amount": 1000,
            "interest": 0,
            "installments": 4,
            "frequency": "monthly",
            "due": "2099-01-31",
        })
        self.assertEqual(response.status_code, 201)
        dates = [
            item["due"]
            for item in self.client.get("/api/data").json["installments"]
        ]
        self.assertEqual(dates, ["2099-01-31", "2099-02-28", "2099-03-31", "2099-04-30"])

    def test_pagamento_atrasado_retorna_valor_com_juros(self):
        self.login_admin()
        client_id = self.create_client()
        response = self.client.post("/api/loans", json={
            "clientId": client_id,
            "amount": 100,
            "interest": 0,
            "installments": 1,
            "frequency": "monthly",
            "due": "2099-01-05",
        })
        loan_id = response.json["loan"]["id"]
        with agiproz.get_db() as db:
            db.execute(
                "UPDATE installments SET due=? WHERE loan_id=? AND number=1",
                ((agiproz.date.today() - agiproz.timedelta(days=1)).isoformat(), loan_id),
            )
        payment = self.client.post("/api/payments", json={"loanId": loan_id})
        self.assertEqual(payment.status_code, 201)
        self.assertEqual(payment.json["payment"]["value"], 110.0)

    def test_recuperacao_de_senha_do_admin(self):
        self.login_admin()
        code_path = agiproz.INSTANCE_DIR / "admin_recovery_code.txt"
        self.assertTrue(code_path.exists())
        code = code_path.read_text(encoding="utf-8").splitlines()[2].strip()
        self.client.post("/api/logout")
        response = self.client.post("/api/admin/recover", json={
            "email": "admin@agiproz.local",
            "recoveryCode": code,
            "password": "NovaSenha@123",
            "password2": "NovaSenha@123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["user"]["role"], "admin")

    def test_reset_operador_preserva_dados_e_forca_troca(self):
        self.login_admin()
        response = self.client.post("/api/users", json={
            "name": "Operador Teste",
            "login": "operador.teste",
            "email": "operador2@agiproz.local",
        })
        self.assertEqual(response.status_code, 201)
        operator = response.json["user"]
        created = operator["created"]
        response = self.client.post(f"/api/users/{operator['id']}/reset-password")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["temporaryPassword"])
        self.assertTrue(response.json["user"]["forcePasswordChange"])
        self.assertEqual(response.json["user"]["created"], created)

    def test_auditoria_exige_admin(self):
        self.login_admin()
        response = self.client.get("/api/audit")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json["logs"]), 1)


if __name__ == "__main__":
    unittest.main()
