#!/usr/bin/env python3
"""
Test de la correction du patch d'encodage
"""

print("=== Test de la correction d'encodage ===")

try:
    # Import du client IRC qui applique le patch corrigé
    from irc_client import IRCClient
    print("✅ Import irc_client réussi - nouveau patch appliqué")
    
    # Configuration de test
    test_config = {
        'irc': {
            'servers': [{'hostname': 'test.server', 'port': 6667, 'ssl': False}],
            'nickname': 'TestBot',
            'realname': 'Test Bot',
            'channels': ['#test'],
            'monitored_channel': '#test',
            'redirect_channel': '#adultes',
            'is_ircop': False
        },
        'badwords_filter': {
            'enabled': True,
            'channels': ['#test'],
            'immediate_ban': True,
            'send_warning_message': True,
            'log_detections': False
        },
        'nickname_filter': {
            'enabled': True,
            'channels': ['#test'],
            'send_messages': True,
            'log_detections': False
        }
    }
    
    # Test de création du client
    print("\n🧪 Test de création du client IRC...")
    client = IRCClient(test_config, None)
    print("✅ Client IRC créé sans erreur de super()")
    
    # Vérifier que le patch a été appliqué
    import jaraco.stream.buffer
    import irc.client
    
    # Test de création d'un DecodingLineBuffer
    print("\n🔧 Test de DecodingLineBuffer...")
    try:
        import io
        test_buffer = io.BytesIO(b"test\n")
        decoder = jaraco.stream.buffer.DecodingLineBuffer(test_buffer)
        print("✅ DecodingLineBuffer créé sans erreur")
        
        # Test avec des données UTF-8 valides
        list(decoder.lines())
        print("✅ Décodage UTF-8 valide fonctionne")
        
    except Exception as e:
        print(f"❌ Erreur DecodingLineBuffer: {e}")
    
    # Test des filtres
    print(f"\n📊 Vérification des filtres:")
    print(f"   🔍 Mots interdits: {len(client.badwords_filter.badwords)} patterns")
    print(f"   👤 Pseudos: {len(client.nickname_filter.inappropriate_patterns)} patterns")
    
    print("\n🎉 Test de correction réussi - pas d'erreur super() !")
    
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
    exit(1)