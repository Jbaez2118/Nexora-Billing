import { useEffect, useState } from 'react';
import { Button, FlatList, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import * as AuthSession from 'expo-auth-session';
import * as WebBrowser from 'expo-web-browser';
import Oibc from './Oibc';
import Config from './Config';

WebBrowser.maybeCompleteAuthSession();

const API = process.env.EXPO_PUBLIC_API_URL;
const KC = process.env.EXPO_PUBLIC_KC_URL as string;
const CLIENT_ID = 'nexora-app';
type Unit = { id: string; parent_id: string | null; kind: string; name: string };

function flatten(units: Unit[], parent: string | null = null, depth = 0): (Unit & { depth: number })[] {
  return units.filter(u => u.parent_id === parent).flatMap(u => [{ ...u, depth }, ...flatten(units, u.id, depth + 1)]);
}

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [err, setErr] = useState('');

  const discovery = AuthSession.useAutoDiscovery(KC);
  const redirectUri = AuthSession.makeRedirectUri();
  const [request, response, promptAsync] = AuthSession.useAuthRequest(
    { clientId: CLIENT_ID, redirectUri, scopes: ['openid'], usePKCE: true },
    discovery
  );

  useEffect(() => {
    if (response?.type === 'success' && request?.codeVerifier && discovery) {
      AuthSession.exchangeCodeAsync(
        { clientId: CLIENT_ID, code: response.params.code, redirectUri, extraParams: { code_verifier: request.codeVerifier } },
        discovery
      ).then(t => setToken(t.accessToken)).catch(e => setErr(String(e)));
    } else if (response?.type === 'error') {
      setErr(String(response.error ?? 'error de login'));
    }
  }, [response]);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/org/units`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => (r.ok ? r.json() : Promise.reject('HTTP ' + r.status)))
      .then(setUnits)
      .catch(e => setErr(String(e)));
  }, [token]);

  return (
    <SafeAreaView style={s.c}>
      <Text style={s.h1}>NexoraBilling</Text>
      {!token ? (
        <Button title="Iniciar sesión" disabled={!request} onPress={() => promptAsync()} />
      ) : (
        <>
          <Button title="Salir" onPress={() => { setToken(null); setUnits([]); }} />
          <Text style={s.h2}>Organigrama</Text>
          <FlatList
            data={flatten(units)}
            keyExtractor={u => u.id}
            ListFooterComponent={<><Oibc token={token} /><Config token={token} /></>}
            renderItem={({ item }) => (
              <View style={{ marginLeft: item.depth * 20, paddingVertical: 4 }}>
                <Text>{item.name} ({item.kind})</Text>
              </View>
            )}
          />
        </>
      )}
      {!!err && <Text style={{ color: 'crimson', marginTop: 12 }}>{err}</Text>}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  c: { flex: 1, padding: 24, paddingTop: 56, backgroundColor: '#fff' },
  h1: { fontSize: 26, fontWeight: '700', marginBottom: 12 },
  h2: { fontSize: 18, fontWeight: '600', marginTop: 16 },
});
