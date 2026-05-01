from sph_client import SchulportalHessenAPI, Cryptor

api = SchulportalHessenAPI()

print(api.login_using_env())

api.benutzer_get_data()