from sph_client import SchulportalHessenAPI, Cryptor

api = SchulportalHessenAPI()

print(api.login_using_env())

api.benutzer_get_data()

print(api.dsb_get_substitution_plan(password="berlin", username="282822"))