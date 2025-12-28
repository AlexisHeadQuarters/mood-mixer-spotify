import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import re

# Sayfa ayarları
st.set_page_config(page_title="Mood Mixer", page_icon="🎧", layout="centered")

# Başlık ve açıklama
st.title("🎧 Mood Mixer")
st.markdown("**Herhangi bir Spotify playlistini istediğin moda göre otomatik karıştır!**")
st.markdown("Mutlu, chill, enerjik, spor, odaklanma... Sen seç, gerisini ben halledeyim 🔥")

# Spotify OAuth ayarları (secrets'tan çekiliyor)
sp_oauth = SpotifyOAuth(
    client_id=st.secrets["SPOTIFY_CLIENT_ID"],
    client_secret=st.secrets["SPOTIFY_CLIENT_SECRET"],
    redirect_uri=st.secrets["SPOTIFY_REDIRECT_URI"],
    scope="playlist-read-private playlist-modify-public playlist-modify-private user-library-read"
)

# Query params'tan code'u al (OAuth callback)
code = st.query_params.get("code")

# Session state ile token yönetimi
if "token_info" not in st.session_state:
    if code:
        token_info = sp_oauth.get_access_token(code, as_dict=True)
        st.session_state.token_info = token_info
        st.rerun()
    else:
        # Login butonu (yeni sekmede açılıyor)
        auth_url = sp_oauth.get_authorize_url()
        st.markdown(
            f"""
            <a href='{auth_url}' target='_blank'>
                <button style="
                    padding: 15px 30px;
                    font-size: 20px;
                    background: #1DB954;
                    color: white;
                    border: none;
                    border-radius: 12px;
                    cursor: pointer;
                ">
                    🔗 Connect with Spotify (Yeni Sekmede Açılır)
                </button>
            </a>
            """,
            unsafe_allow_html=True
        )
        st.info("Bağlanmak için butona tıkla, Spotify izin ekranı yeni sekmede açılacak.")
        st.stop()

# Token varsa refresh kontrolü yap
token_info = st.session_state.token_info
if sp_oauth.is_token_expired(token_info):
    token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
    st.session_state.token_info = token_info

# Spotify client oluştur
sp = spotipy.Spotify(auth=token_info['access_token'])
user = sp.current_user()
st.success(f"✅ Bağlandı: **{user['display_name']}** ({user['id']})")

# Kullanıcı arayüzü
playlist_url = st.text_input("📋 Spotify playlist linkini buraya yapıştır:", placeholder="https://open.spotify.com/playlist/...")
mood = st.selectbox("🌈 Hedef mood'un ne olsun?", [
    "Happy 😄",
    "Chill 😌",
    "Energetic ⚡",
    "Workout 💪",
    "Focus 🧠",
    "Party 🎉",
    "Sad ☔",
    "Romantic ❤️"
])

# Mood hedef özellikleri
mood_targets = {
    "Happy 😄": {"valence": 0.8, "energy": 0.7},
    "Chill 😌": {"valence": 0.5, "energy": 0.3},
    "Energetic ⚡": {"energy": 0.9, "danceability": 0.8},
    "Workout 💪": {"energy": 0.95, "tempo": 130, "danceability": 0.7},
    "Focus 🧠": {"energy": 0.4, "instrumentalness": 0.8},
    "Party 🎉": {"danceability": 0.9, "energy": 0.9},
    "Sad ☔": {"valence": 0.2, "energy": 0.4},
    "Romantic ❤️": {"valence": 0.6, "acousticness": 0.7}
}

if st.button("🔥 MIX IT! Let's Do It!") and playlist_url:
    with st.spinner("Playlist analiz ediliyor ve yeni vibe oluşturuluyor..."):
        try:
            # Playlist ID'yi güvenli şekilde çıkar (regex ile)
            match = re.search(r"playlist[/:]([A-Za-z0-9]{22})(?:\?|$)", playlist_url)
            if not match:
                st.error("Geçersiz Spotify playlist linki! Lütfen doğru formatta bir link yapıştırın.\n\nÖrnek: https://open.spotify.com/playlist/37i9dQZF1DX... ")
                st.stop()
            
            playlist_id = match.group(1)

            # Playlist şarkılarını al
            tracks = sp.playlist_tracks(playlist_id)["items"]
            track_ids = [item["track"]["id"] for item in tracks if item["track"] and item["track"]["id"]]
            
            if not track_ids:
                st.error("Bu playlistte şarkı bulunamadı veya erişim izniniz yok. Playlist'in herkese açık olduğundan emin olun.")
                st.stop()

            # Audio features al
            features = sp.audio_features(track_ids)

            # None gelen feature'ları filtrele
            valid_pairs = [(tid, feat) for tid, feat in zip(track_ids, features) if feat is not None]
            if not valid_pairs:
                st.error("Şarkıların ses özellikleri alınamadı.")
                st.stop()

            track_ids, features = zip(*valid_pairs)

            target = mood_targets[mood]

            # Benzerlik skoru (Euclidean distance)
            def similarity(feat):
                score = 0
                for key, val in target.items():
                    if key in feat and feat[key] is not None:
                        # Tempo için özel işlem (eğer varsa)
                        if key == "tempo" and val > 100:
                            diff = min(abs(feat[key] - val), abs(feat[key] - (val - 20)))  # tempo yakınlığı
                        else:
                            diff = feat[key] - val
                        score += diff ** 2
                return score ** 0.5

            # En yakın 50 şarkıyı seç
            scored = sorted(zip(track_ids, features), key=lambda x: similarity(x[1]))
            recommended_ids = [tid for tid, _ in scored[:50]]

            # Yeni playlist oluştur
            new_playlist_name = f"Mood Mix: {mood} 🎯"
            new_playlist = sp.user_playlist_create(
                user=user["id"],
                name=new_playlist_name,
                public=True,
                description="Mood Mixer ile oluşturuldu 🎧 https://mixer.alxishq.site"
            )

            # Şarkıları ekle (100'erli parçalar halinde, Spotify limiti)
            for i in range(0, len(recommended_ids), 100):
                sp.playlist_add_items(new_playlist["id"], recommended_ids[i:i+100])

            st.success("✅ Yeni playlist hazırlandı!")
            st.balloons()
            st.markdown(f"### 🎶 **{new_playlist['name']}** ({len(recommended_ids)} şarkı)")
            st.markdown(f"→ [Spotify'da Aç]({new_playlist['external_urls']['spotify']})")

        except spotipy.SpotifyException as e:
            st.error(f"Spotify hatası: {e.msg if hasattr(e, 'msg') else str(e)}")
            st.info("Playlist herkese açık mı? Veya link doğru mu?")
        except Exception as e:
            st.error(f"Beklenmeyen hata: {str(e)}")
            st.info("Linki ve bağlantıyı kontrol edin.")

# Alt bilgi
st.caption("Made with ❤️ by Sad_Always – A AlexisHq project: https://alxishq.site")
