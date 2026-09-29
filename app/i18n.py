"""User-facing text for every supported farmer language.

Language codes: "en" (English), "pa" (Punjabi, Gurmukhi), "hinglish" (Hindi in Roman script), "hi" (Hindi, Devanagari).
"""

from typing import Dict, List

# Dropdown order: English, Punjabi, Hinglish, Hindi
LANGUAGES: Dict[str, str] = {
    "en": "English",
    "pa": "ਪੰਜਾਬੀ (Punjabi)",
    "hinglish": "Hinglish",
    "hi": "हिन्दी (Hindi)",
}

DEFAULT_LANGUAGE = "en"

# Instruction appended to the LLM prompt so the answer comes back in the farmer's language
LLM_LANGUAGE_INSTRUCTIONS: Dict[str, str] = {
    "en": "Write the entire answer in simple English that a farmer can easily understand.",
    "pa": "Write the entire answer in Punjabi using Gurmukhi script.",
    "hinglish": (
        "Write the entire answer in Hinglish: Hindi written in Roman (English) letters, the way farmers "
        "type on WhatsApp (e.g. 'Sarson mein chepa ke liye spray tabhi karein jab...'). Do not use Devanagari script."
    ),
    "hi": "Write the entire answer in Hindi using Devanagari script.",
}

STRINGS: Dict[str, Dict[str, str]] = {
    # ------------------------------------------------------------------ pipeline replies
    "empty_query": {
        "en": "Please ask a question about your crop or farming.",
        "pa": "ਕਿਰਪਾ ਕਰਕੇ ਆਪਣੀ ਫ਼ਸਲ ਜਾਂ ਖੇਤੀ ਨਾਲ ਸਬੰਧਤ ਕੋਈ ਸਵਾਲ ਪੁੱਛੋ।",
        "hinglish": "Kripya apni fasal ya kheti se juda koi sawal poochein.",
        "hi": "कृपया अपनी फसल या कृषि से संबंधित कोई प्रश्न पूछें। (Please enter your agricultural query.)",
    },
    "greeting": {
        "en": (
            "Namaste! I am KisanSahayak, your farming assistant.\n\n"
            "I can help with pests, diseases, fertilizer, seeds, weather and pesticide safety for wheat, "
            "mustard, paddy, cotton and other crops. You can type your question or ask by voice."
        ),
        "pa": (
            "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਕਿਸਾਨ ਵੀਰੋ! ਮੈਂ ਕਿਸਾਨ ਸਹਾਇਕ (KisanSahayak) ਹਾਂ।\n\n"
            "ਮੈਂ ਕਣਕ, ਸਰ੍ਹੋਂ, ਝੋਨਾ, ਨਰਮਾ ਅਤੇ ਹੋਰ ਫ਼ਸਲਾਂ ਵਿੱਚ ਕੀੜੇ, ਬਿਮਾਰੀਆਂ, ਖਾਦ, ਬੀਜ, ਮੌਸਮ ਅਤੇ ਕੀਟਨਾਸ਼ਕ ਸੁਰੱਖਿਆ "
            "ਬਾਰੇ ਤੁਹਾਡੀ ਮਦਦ ਲਈ ਤਿਆਰ ਹਾਂ। ਤੁਸੀਂ ਆਪਣਾ ਸਵਾਲ ਲਿਖ ਕੇ ਜਾਂ ਬੋਲ ਕੇ ਪੁੱਛ ਸਕਦੇ ਹੋ।"
        ),
        "hinglish": (
            "Namaste kisan bhai! Main KisanSahayak hoon.\n\n"
            "Main gehun, sarson, dhan, kapas aur doosri faslon mein keet, rog, khad, beej, mausam aur "
            "keetnashak suraksha se jude sawalon mein aapki madad ke liye taiyaar hoon. "
            "Aap apna sawal likh kar ya bol kar pooch sakte hain."
        ),
        "hi": (
            "नमस्ते किसान भाई! मैं किसान सहायक (KisanSahayak) हूँ।\n\n"
            "मैं गेहूं, सरसों, धान, कपास और अन्य फसलों में कीट, रोग, खाद, बीज, मौसम एवं कृषि सुरक्षा "
            "से संबंधित आपकी सहायता के लिए तैयार हूँ। आप अपनी समस्या लिखकर या बोलकर पूछ सकते हैं।"
        ),
    },
    "out_of_scope": {
        "en": (
            "This question does not seem to be about farming. KisanSahayak only answers questions about "
            "crop care, pest and disease control, fertilizer, weather and pesticide safety. Please ask a farming question."
        ),
        "pa": (
            "ਇਹ ਸਵਾਲ ਖੇਤੀਬਾੜੀ ਨਾਲ ਸਬੰਧਤ ਨਹੀਂ ਜਾਪਦਾ। ਕਿਸਾਨ ਸਹਾਇਕ ਸਿਰਫ਼ ਫ਼ਸਲਾਂ ਦੀ ਦੇਖਭਾਲ, ਕੀੜੇ ਅਤੇ ਬਿਮਾਰੀਆਂ ਦੀ ਰੋਕਥਾਮ, "
            "ਖਾਦ, ਮੌਸਮ ਅਤੇ ਕੀਟਨਾਸ਼ਕ ਸੁਰੱਖਿਆ ਬਾਰੇ ਸਵਾਲਾਂ ਦੇ ਜਵਾਬ ਦਿੰਦਾ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਖੇਤੀ ਨਾਲ ਸਬੰਧਤ ਸਵਾਲ ਪੁੱਛੋ।"
        ),
        "hinglish": (
            "Yeh sawal kheti se juda nahi lagta. KisanSahayak sirf fasal ki dekhbhal, keet aur rog niyantran, "
            "khad, mausam aur keetnashak suraksha ke sawalon ke liye hai. Kripya kheti se juda sawal poochein."
        ),
        "hi": (
            "यह प्रश्न कृषि क्षेत्र से संबंधित नहीं प्रतीत होता है। "
            "किसान सहायक केवल फसलों की देखभाल, रोग नियंत्रण, उर्वरक, मौसम और कृषि सुरक्षा संबंधी "
            "प्रश्नों के लिए समर्पित है। कृपया कृषि से संबंधित प्रश्न पूछें।"
        ),
    },
    "stt_failed": {
        "en": "Sorry, I couldn't understand the voice message right now. Please try again, or type your question in the box.",
        "pa": "ਮਾਫ਼ ਕਰਨਾ, ਮੈਂ ਇਸ ਵੇਲੇ ਆਵਾਜ਼ ਸੁਨੇਹਾ ਸਮਝ ਨਹੀਂ ਸਕਿਆ। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ, ਜਾਂ ਆਪਣਾ ਸਵਾਲ ਬਾਕਸ ਵਿੱਚ ਲਿਖੋ।",
        "hinglish": "Maaf kijiye, abhi voice message samajh nahi paya. Kripya dobara koshish karein, ya apna sawal box mein likhein.",
        "hi": "क्षमा करें, अभी आवाज़ संदेश समझ नहीं पाया। कृपया फिर से कोशिश करें, या अपना प्रश्न बॉक्स में लिखें।",
    },
    "processing_error": {
        "en": "Your question could not be processed due to a technical error: {error}. Please try again or contact your local agriculture expert.",
        "pa": "ਤਕਨੀਕੀ ਗੜਬੜ ਕਾਰਨ ਤੁਹਾਡਾ ਸਵਾਲ ਪੂਰਾ ਨਹੀਂ ਹੋ ਸਕਿਆ: {error}। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ ਜਾਂ ਆਪਣੇ ਨੇੜਲੇ ਖੇਤੀ ਮਾਹਿਰ ਨਾਲ ਸੰਪਰਕ ਕਰੋ।",
        "hinglish": "Technical error ki wajah se aapka sawal process nahi ho paya: {error}. Kripya dobara koshish karein ya apne local krishi expert se sampark karein.",
        "hi": "तकनीकी त्रुटि के कारण आपका प्रश्न संसाधित नहीं हो सका: {error}। कृपया पुनः प्रयास करें या अपने स्थानीय कृषि विशेषज्ञ से संपर्क करें।",
    },
    "error_handling_active": {
        "en": "Error handling active.",
        "pa": "ਗੜਬੜ ਸੰਭਾਲ ਪ੍ਰਣਾਲੀ ਸਰਗਰਮ।",
        "hinglish": "Error handling active.",
        "hi": "त्रुटि प्रबंधन प्रणाली सक्रिय।",
    },
    "no_verified_info": {
        "en": (
            "Sorry, we do not have verified ICAR/PAU documents on this question. For correct information and "
            "diagnosis, please contact your nearest Krishi Vigyan Kendra (KVK) or agriculture officer."
        ),
        "pa": (
            "ਮਾਫ਼ ਕਰਨਾ, ਤੁਹਾਡੇ ਸਵਾਲ ਬਾਰੇ ਸਾਡੇ ਕੋਲ ਪ੍ਰਮਾਣਿਤ ICAR/PAU ਜਾਣਕਾਰੀ ਉਪਲਬਧ ਨਹੀਂ ਹੈ। ਸਹੀ ਜਾਣਕਾਰੀ ਅਤੇ ਇਲਾਜ ਲਈ "
            "ਕਿਰਪਾ ਕਰਕੇ ਆਪਣੇ ਨੇੜਲੇ ਕ੍ਰਿਸ਼ੀ ਵਿਗਿਆਨ ਕੇਂਦਰ (KVK) ਜਾਂ ਖੇਤੀਬਾੜੀ ਅਫ਼ਸਰ ਨਾਲ ਸੰਪਰਕ ਕਰੋ।"
        ),
        "hinglish": (
            "Maaf kijiye, is sawal par hamare paas pramanit ICAR/PAU jaankari uplabdh nahi hai. Sahi jaankari "
            "aur ilaaj ke liye kripya apne nazdeeki Krishi Vigyan Kendra (KVK) ya krishi adhikari se sampark karein."
        ),
        "hi": (
            "क्षमा करें, आपके पूछे गए प्रश्न के संबंध में हमारे पास प्रमाणित ICAR/PAU दस्तावेज़ उपलब्ध नहीं हैं। "
            "कृपया सही जानकारी एवं निदान हेतु अपने नजदीकी कृषि विज्ञान केंद्र (KVK) या कृषि अधिकारी से संपर्क करें।"
        ),
    },
    # ------------------------------------------------------------------ offline template headings
    "crop_advisory": {"en": "Crop Advisory", "pa": "ਫ਼ਸਲ ਸਲਾਹ", "hinglish": "Fasal Salah", "hi": "फसल परामर्श"},
    "identification": {
        "en": "Identification & Symptoms",
        "pa": "ਪਛਾਣ ਅਤੇ ਲੱਛਣ",
        "hinglish": "Pehchaan aur Lakshan",
        "hi": "पहचान एवं लक्षण (Identification)",
    },
    "recommended_control": {
        "en": "Recommended Control & Dosage",
        "pa": "ਸਿਫ਼ਾਰਸ਼ ਕੀਤਾ ਇਲਾਜ ਅਤੇ ਖੁਰਾਕ",
        "hinglish": "Sujhaya Ilaaj aur Dose",
        "hi": "अनुशंसित उपचार एवं खुराक (Recommended Control & Dosage)",
    },
    "preventive_measures": {
        "en": "Preventive Measures",
        "pa": "ਰੋਕਥਾਮ ਅਤੇ ਸਾਵਧਾਨੀਆਂ",
        "hinglish": "Rokthaam aur Savdhaniyan",
        "hi": "रोकथाम एवं सावधानियां (Preventive Measures)",
    },
    "special_warning": {
        "en": "Special Statutory Warning",
        "pa": "ਵਿਸ਼ੇਸ਼ ਕਾਨੂੰਨੀ ਚੇਤਾਵਨੀ",
        "hinglish": "Vishesh Kanooni Chetavani",
        "hi": "विशेष वैधानिक चेतावनी",
    },
    # ------------------------------------------------------------------ weather
    "weather_advisory_title": {
        "en": "Farm Weather Advisory",
        "pa": "ਖੇਤੀ ਮੌਸਮ ਸਲਾਹ",
        "hinglish": "Krishi Mausam Salah",
        "hi": "कृषि मौसम परामर्श",
    },
    "temperature": {"en": "Temperature", "pa": "ਤਾਪਮਾਨ", "hinglish": "Taapmaan", "hi": "तापमान"},
    "wind_speed": {"en": "Wind Speed", "pa": "ਹਵਾ ਦੀ ਰਫ਼ਤਾਰ", "hinglish": "Hawa ki Raftaar", "hi": "हवा की गति"},
    "rain_chance": {"en": "Rain Chance", "pa": "ਮੀਂਹ ਦੀ ਸੰਭਾਵਨਾ", "hinglish": "Baarish ki Sambhavna", "hi": "वर्षा की संभावना"},
    "humidity": {"en": "Humidity", "pa": "ਨਮੀ", "hinglish": "Nami", "hi": "सापेक्ष आर्द्रता"},
    "spray_advisory": {"en": "Spray Advisory", "pa": "ਛਿੜਕਾਅ ਸਲਾਹ", "hinglish": "Chhidkaav Salah", "hi": "छिड़काव परामर्श"},
    "irrigation_advice": {"en": "Irrigation Advice", "pa": "ਸਿੰਚਾਈ ਸਲਾਹ", "hinglish": "Sinchai Salah", "hi": "सिंचाई सलाह"},
    "weather_summary": {
        "en": "{place}: {temp}°C, humidity {humidity}%, wind {wind} km/h, and a {rain}% chance of rain in the next 12 hours.",
        "pa": "{place}: ਤਾਪਮਾਨ {temp}°C, ਨਮੀ {humidity}%, ਹਵਾ {wind} km/h, ਅਤੇ ਅਗਲੇ 12 ਘੰਟਿਆਂ ਵਿੱਚ ਮੀਂਹ ਦੀ ਸੰਭਾਵਨਾ {rain}% ਹੈ।",
        "hinglish": "{place}: taapmaan {temp}°C, nami {humidity}%, hawa {wind} km/h, aur agle 12 ghanton mein baarish ki sambhavna {rain}% hai.",
        "hi": "{place}: तापमान {temp}°C, नमी {humidity}%, हवा {wind} km/h, और अगले 12 घंटों में बारिश की संभावना {rain}% है।",
    },
    "location_default": {
        "en": "No place was recognised in your question, so this shows **{default}**. Mention your district, e.g. \"weather in Sangrur\".",
        "pa": "ਤੁਹਾਡੇ ਸਵਾਲ ਵਿੱਚ ਕੋਈ ਥਾਂ ਨਹੀਂ ਪਛਾਣੀ ਗਈ, ਇਸ ਲਈ ਇਹ **{default}** ਦਾ ਮੌਸਮ ਹੈ। ਆਪਣਾ ਜ਼ਿਲ੍ਹਾ ਦੱਸੋ, ਜਿਵੇਂ \"ਸੰਗਰੂਰ ਵਿੱਚ ਮੌਸਮ\"।",
        "hinglish": "Aapke sawal mein koi jagah pehchani nahi gayi, isliye yeh **{default}** ka mausam hai. Apna zila batayein, jaise \"Sangrur mein mausam\".",
        "hi": "आपके प्रश्न में कोई स्थान नहीं पहचाना गया, इसलिए यह **{default}** का मौसम है। अपना ज़िला बताएँ, जैसे \"संगरूर में मौसम\"।",
    },
    "location_not_found": {
        "en": "Couldn't find \"{place}\", so this shows **{default}** instead. Try your district name, e.g. \"weather in Sangrur\".",
        "pa": "\"{place}\" ਨਹੀਂ ਲੱਭਿਆ, ਇਸ ਲਈ ਇਹ **{default}** ਦਾ ਮੌਸਮ ਹੈ। ਆਪਣੇ ਜ਼ਿਲ੍ਹੇ ਦਾ ਨਾਮ ਲਿਖੋ, ਜਿਵੇਂ \"ਸੰਗਰੂਰ ਵਿੱਚ ਮੌਸਮ\"।",
        "hinglish": "\"{place}\" nahi mila, isliye yeh **{default}** ka mausam hai. Apne zile ka naam likhein, jaise \"Sangrur mein mausam\".",
        "hi": "\"{place}\" नहीं मिला, इसलिए यह **{default}** का मौसम है। अपने ज़िले का नाम लिखें, जैसे \"संगरूर में मौसम\"।",
    },
    "spray_rain": {
        "en": "Postpone spraying: rain is likely in the next 12-24 hours and could wash the chemical off.",
        "pa": "ਛਿੜਕਾਅ ਅੱਗੇ ਪਾਓ: ਅਗਲੇ 12-24 ਘੰਟਿਆਂ ਵਿੱਚ ਮੀਂਹ ਦੀ ਸੰਭਾਵਨਾ ਹੈ। ਦਵਾਈ ਧੋਤੀ ਜਾਣ ਦਾ ਖ਼ਤਰਾ ਹੈ।",
        "hinglish": "Chhidkaav aage badhayein: agle 12-24 ghanton mein baarish ki sambhavna hai. Dawa dhul jaane ka khatra hai.",
        "hi": "छिड़काव स्थगित करें (Postpone Spray): अगले 12-24 घंटों में वर्षा की संभावना है। दवा धुलने का जोखिम है।",
    },
    "spray_wind": {
        "en": "Strong wind ({wind} km/h): do not spray pesticides. Spray drift can carry the chemical away and cause damage.",
        "pa": "ਤੇਜ਼ ਹਵਾ ({wind} km/h): ਕੀਟਨਾਸ਼ਕ ਦਾ ਛਿੜਕਾਅ ਨਾ ਕਰੋ। ਹਵਾ ਨਾਲ ਦਵਾਈ ਉੱਡਣ (spray drift) ਅਤੇ ਨੁਕਸਾਨ ਦਾ ਖ਼ਤਰਾ ਹੈ।",
        "hinglish": "Tez hawa ({wind} km/h): keetnashak ka chhidkaav na karein. Hawa se dawa udne (spray drift) aur nuksaan ka khatra hai.",
        "hi": "तेज हवा ({wind} km/h): कीटनाशक छिड़काव न करें। हवा के बहाव (spray drift) से दवा उड़ने और नुकसान का खतरा है।",
    },
    "spray_ok": {
        "en": "Good time to spray: wind speed is normal. Spray between 8-11 AM or after 3:30 PM.",
        "pa": "ਛਿੜਕਾਅ ਲਈ ਢੁਕਵਾਂ ਸਮਾਂ: ਹਵਾ ਦੀ ਰਫ਼ਤਾਰ ਆਮ ਹੈ। ਸਵੇਰੇ 8-11 ਵਜੇ ਜਾਂ ਸ਼ਾਮ 3:30 ਵਜੇ ਤੋਂ ਬਾਅਦ ਛਿੜਕਾਅ ਕਰੋ।",
        "hinglish": "Chhidkaav ke liye sahi samay: hawa ki raftaar normal hai. Subah 8-11 baje ya shaam 3:30 baje ke baad chhidkaav karein.",
        "hi": "छिड़काव हेतु अनुकूल समय: हवा की गति सामान्य है। सुबह 8-11 बजे या शाम 3:30 बजे के बाद छिड़काव करें।",
    },
    "irrigation_stop": {
        "en": "Hold irrigation: enough rain is likely soon, which could cause waterlogging.",
        "pa": "ਸਿੰਚਾਈ ਰੋਕੋ: ਜਲਦੀ ਚੰਗੇ ਮੀਂਹ ਦੀ ਸੰਭਾਵਨਾ ਹੈ, ਜਿਸ ਨਾਲ ਖੇਤ ਵਿੱਚ ਪਾਣੀ ਖੜ੍ਹ ਸਕਦਾ ਹੈ।",
        "hinglish": "Sinchai rokein: jaldi achhi baarish ki sambhavna hai, jisse khet mein paani bhar sakta hai.",
        "hi": "सिंचाई रोकें: निकट समय में पर्याप्त वर्षा की संभावना है, जिससे जलभराव हो सकता है।",
    },
    "irrigation_light": {
        "en": "Light irrigation needed: high temperature is drying the soil quickly. Irrigate lightly in the evening.",
        "pa": "ਹਲਕੀ ਸਿੰਚਾਈ ਜ਼ਰੂਰੀ: ਵੱਧ ਤਾਪਮਾਨ ਕਾਰਨ ਨਮੀ ਤੇਜ਼ੀ ਨਾਲ ਘਟ ਰਹੀ ਹੈ। ਸ਼ਾਮ ਵੇਲੇ ਹਲਕੀ ਸਿੰਚਾਈ ਕਰੋ।",
        "hinglish": "Halki sinchai zaroori: zyada taapmaan ki wajah se nami tezi se ghat rahi hai. Shaam ke samay halki sinchai karein.",
        "hi": "हल्की सिंचाई आवश्यक: उच्च तापमान के कारण नमी तेजी से घट रही है। शाम के समय हल्की सिंचाई करें।",
    },
    "irrigation_normal": {
        "en": "Normal irrigation: check soil moisture in the field and irrigate as needed.",
        "pa": "ਆਮ ਸਿੰਚਾਈ: ਖੇਤ ਦੀ ਮਿੱਟੀ ਵਿੱਚ ਨਮੀ ਦੇਖ ਕੇ ਲੋੜ ਅਨੁਸਾਰ ਸਿੰਚਾਈ ਕਰੋ।",
        "hinglish": "Normal sinchai: khet ki mitti mein nami dekh kar zaroorat ke hisaab se sinchai karein.",
        "hi": "सामान्य सिंचाई: खेत की मिट्टी में नमी की स्थिति देखकर आवश्यकतानुसार सिंचाई करें।",
    },
    "fallback_spray": {
        "en": "Favourable weather (safe estimate): pesticide or fertilizer can be sprayed when the wind is calm.",
        "pa": "ਢੁਕਵਾਂ ਮੌਸਮ (ਸੁਰੱਖਿਅਤ ਅੰਦਾਜ਼ਾ): ਸ਼ਾਂਤ ਹਵਾ ਵੇਲੇ ਕੀਟਨਾਸ਼ਕ ਜਾਂ ਖਾਦ ਦਾ ਛਿੜਕਾਅ ਕੀਤਾ ਜਾ ਸਕਦਾ ਹੈ।",
        "hinglish": "Anukool mausam (surakshit andaaza): shaant hawa ke samay keetnashak ya khad ka chhidkaav kiya ja sakta hai.",
        "hi": "अनुकूल मौसम (सुरक्षित अनुमानित): शांत हवा के समय कीटनाशक या खाद का छिड़काव किया जा सकता है।",
    },
    "fallback_irrigation": {
        "en": "Normal irrigation: plan irrigation around the crop's critical growth stages.",
        "pa": "ਆਮ ਸਿੰਚਾਈ: ਫ਼ਸਲ ਦੀਆਂ ਨਾਜ਼ੁਕ ਅਵਸਥਾਵਾਂ ਅਨੁਸਾਰ ਸਿੰਚਾਈ ਦੀ ਯੋਜਨਾ ਬਣਾਓ।",
        "hinglish": "Normal sinchai: fasal ki zaroori avasthaon ke hisaab se sinchai ki yojana banayein.",
        "hi": "सामान्य सिंचाई: फसल की क्रांतिक अवस्था के अनुसार सिंचाई की योजना बनाएं।",
    },
    # ------------------------------------------------------------------ safety guardrails
    "statutory_disclaimer": {
        "en": (
            "Statutory Disclaimer: Always check the label and dose on the bottle before spraying any pesticide "
            "or chemical. Always wear safety gear (mask and gloves). For detailed advice, contact your local "
            "Krishi Vigyan Kendra (KVK)."
        ),
        "pa": (
            "ਕਾਨੂੰਨੀ ਸੂਚਨਾ / Statutory Disclaimer: ਕਿਸੇ ਵੀ ਕੀਟਨਾਸ਼ਕ ਜਾਂ ਰਸਾਇਣ ਦਾ ਛਿੜਕਾਅ ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ ਬੋਤਲ ਉੱਤੇ ਦਿੱਤਾ "
            "ਲੇਬਲ ਅਤੇ ਖੁਰਾਕ ਜ਼ਰੂਰ ਪੜ੍ਹੋ। ਹਮੇਸ਼ਾ ਸੁਰੱਖਿਆ ਕਿੱਟ (ਮਾਸਕ ਅਤੇ ਦਸਤਾਨੇ) ਪਾਓ। ਵਧੇਰੇ ਸਲਾਹ ਲਈ ਆਪਣੇ ਨੇੜਲੇ "
            "ਕ੍ਰਿਸ਼ੀ ਵਿਗਿਆਨ ਕੇਂਦਰ (KVK) ਨਾਲ ਸੰਪਰਕ ਕਰੋ।"
        ),
        "hinglish": (
            "Statutory Disclaimer: Kisi bhi keetnashak ya chemical ka chhidkaav karne se pehle bottle par diya "
            "label aur dose zaroor check karein. Hamesha suraksha kit (mask aur dastane) pehnein. Vistaar se salah "
            "ke liye apne local Krishi Vigyan Kendra (KVK) se sampark karein."
        ),
        "hi": (
            "वैधानिक सूचना / Statutory Disclaimer: कीटनाशक या रासायनिक छिड़काव से पहले बोतल पर दिए गए लेबल और "
            "खुराक की जांच अवश्य करें। हमेशा सुरक्षा किट (मास्क एवं दस्ताने) पहनें। "
            "विस्तृत परामर्श हेतु अपने स्थानीय कृषि विज्ञान केंद्र (KVK) से संपर्क करें।"
        ),
    },
    "monocrotophos_warning": {
        "en": (
            "Important Safety Warning (CIBRC): Monocrotophos is completely banned in India on vegetables and "
            "fruits. It is highly toxic. Use only safer alternatives recommended by ICAR/PAU (such as Thiamethoxam "
            "or neem extract)."
        ),
        "pa": (
            "ਜ਼ਰੂਰੀ ਸੁਰੱਖਿਆ ਚੇਤਾਵਨੀ (CIBRC): ਮੋਨੋਕ੍ਰੋਟੋਫ਼ਾਸ (Monocrotophos) ਭਾਰਤ ਵਿੱਚ ਸਬਜ਼ੀਆਂ ਅਤੇ ਫਲਾਂ ਉੱਤੇ ਪੂਰੀ "
            "ਤਰ੍ਹਾਂ ਪਾਬੰਦੀਸ਼ੁਦਾ ਹੈ। ਇਹ ਬਹੁਤ ਜ਼ਹਿਰੀਲਾ ਹੈ। ਇਸ ਦੀ ਥਾਂ ICAR/PAU ਵੱਲੋਂ ਸਿਫ਼ਾਰਸ਼ ਕੀਤੇ ਸੁਰੱਖਿਅਤ ਬਦਲ "
            "(ਜਿਵੇਂ Thiamethoxam ਜਾਂ ਨਿੰਮ ਦਾ ਅਰਕ) ਹੀ ਵਰਤੋ।"
        ),
        "hinglish": (
            "Zaroori Suraksha Chetavani (CIBRC): Monocrotophos Bharat mein sabziyon aur phalon par poori tarah "
            "pratibandhit (banned) hai. Yeh bahut zehreela hai. Iski jagah ICAR/PAU dwara sujhaye surakshit vikalp "
            "(jaise Thiamethoxam ya neem ka ark) hi istemaal karein."
        ),
        "hi": (
            "महत्वपूर्ण सुरक्षा चेतावनी (CIBRC): मोनोक्रोटोफॉस (Monocrotophos) भारत में सब्जियों और फलों पर "
            "पूर्णतः प्रतिबंधित है। इसका अत्यधिक जहरीला प्रभाव होता है। इसके स्थान पर ICAR/PAU द्वारा अनुशंसित "
            "सुरक्षित विकल्प (जैसे थायमेथॉक्सम या नीम अर्क) का ही उपयोग करें।"
        ),
    },
    "endosulfan_warning": {
        "en": (
            "Statutory Warning (CIBRC): Endosulfan is completely banned in India by the Supreme Court and the "
            "Central Insecticides Board. Buying, selling or using it is a punishable offence."
        ),
        "pa": (
            "ਕਾਨੂੰਨੀ ਚੇਤਾਵਨੀ (CIBRC): ਐਂਡੋਸਲਫ਼ਾਨ (Endosulfan) ਉੱਤੇ ਭਾਰਤ ਵਿੱਚ ਸੁਪਰੀਮ ਕੋਰਟ ਅਤੇ ਕੇਂਦਰੀ ਕੀਟਨਾਸ਼ਕ ਬੋਰਡ "
            "ਵੱਲੋਂ ਪੂਰੀ ਪਾਬੰਦੀ ਹੈ। ਇਸ ਨੂੰ ਖ਼ਰੀਦਣਾ, ਵੇਚਣਾ ਜਾਂ ਵਰਤਣਾ ਸਜ਼ਾਯੋਗ ਅਪਰਾਧ ਹੈ।"
        ),
        "hinglish": (
            "Kanooni Chetavani (CIBRC): Endosulfan par Bharat mein Supreme Court aur Central Insecticides Board "
            "ne poori tarah pratibandh (ban) lagaya hai. Iski khareed, bikri ya istemaal dandniya apradh hai."
        ),
        "hi": (
            "वैधानिक चेतावनी (CIBRC): एंडोसल्फान (Endosulfan) भारत में सर्वोच्च न्यायालय और केंद्रीय कीटनाशक बोर्ड "
            "द्वारा पूर्ण रूप से प्रतिबंधित (Banned) है। इसका क्रय, विक्रय एवं उपयोग दंडनीय अपराध है।"
        ),
    },
    # ------------------------------------------------------------------ voice output
    "tts_see_screen": {
        "en": "... See the screen for full details.",
        "pa": "... ਪੂਰੀ ਜਾਣਕਾਰੀ ਸਕਰੀਨ ਉੱਤੇ ਦੇਖੋ।",
        "hinglish": "... Poori jaankari screen par dekhein.",
        "hi": "... विस्तृत जानकारी स्क्रीन पर देखें।",
    },
    # ------------------------------------------------------------------ web UI
    "language_label": {lang: "🌐 Language / ਭਾਸ਼ਾ / भाषा" for lang in LANGUAGES},
    "subtitle": {
        "en": "Verified crop advice from agricultural research (ICAR/PAU) and live weather",
        "pa": "ਪ੍ਰਮਾਣਿਤ ਖੇਤੀ ਖੋਜ (ICAR/PAU) ਅਤੇ ਮੌਸਮ ਅਧਾਰਿਤ ਸੁਰੱਖਿਅਤ ਫ਼ਸਲ ਸਲਾਹ",
        "hinglish": "Pramanit krishi research (ICAR/PAU) aur mausam par aadharit surakshit fasal salah",
        "hi": "प्रमाणित कृषि अनुसंधान (ICAR/PAU) एवं मौसम आधारित सुरक्षित फसल परामर्श",
    },
    "tab_text": {"en": "✍️ Type your question", "pa": "✍️ ਲਿਖ ਕੇ ਪੁੱਛੋ", "hinglish": "✍️ Likh kar poochein", "hi": "✍️ लिखकर पूछें"},
    "tab_voice": {"en": "🎙️ Ask by voice", "pa": "🎙️ ਬੋਲ ਕੇ ਪੁੱਛੋ", "hinglish": "🎙️ Bol kar poochein", "hi": "🎙️ बोलकर पूछें"},
    "input_label": {
        "en": "Ask about your crop, pest, disease or the weather:",
        "pa": "ਆਪਣੀ ਫ਼ਸਲ, ਬਿਮਾਰੀ ਜਾਂ ਮੌਸਮ ਬਾਰੇ ਪੁੱਛੋ:",
        "hinglish": "Apni fasal, rog ya mausam ke baare mein poochein:",
        "hi": "अपनी फसल, रोग या मौसम के बारे में पूछें:",
    },
    "input_placeholder": {
        "en": "e.g. How do I control aphids in mustard? or What's the weather in Ludhiana today?",
        "pa": "ਜਿਵੇਂ: ਲੁਧਿਆਣਾ ਵਿੱਚ ਅੱਜ ਮੌਸਮ ਕਿਹੋ ਜਿਹਾ ਹੈ? ਜਾਂ ਸਰ੍ਹੋਂ ਵਿੱਚ ਚੇਪੇ ਦੀ ਰੋਕਥਾਮ ਕਿਵੇਂ ਕਰੀਏ?",
        "hinglish": "Jaise: Ludhiana mein aaj mausam kaisa hai? ya sarson mein chepa ka ilaj kya hai?",
        "hi": "उदा: लुधियाना में आज मौसम कैसा है? या सरसों में माहू की रोकथाम कैसे करें?",
    },
    "voice_info": {
        "en": "🎙️ Upload a recorded voice note (.wav / .mp3):",
        "pa": "🎙️ ਰਿਕਾਰਡ ਕੀਤਾ ਆਡੀਓ (.wav / .mp3) ਅੱਪਲੋਡ ਕਰੋ:",
        "hinglish": "🎙️ Record kiya hua audio (.wav / .mp3) upload karein:",
        "hi": "🎙️ रिकॉर्ड किया गया ऑडियो (.wav / .mp3) अपलोड करें:",
    },
    "upload_label": {"en": "Choose audio file:", "pa": "ਆਡੀਓ ਫ਼ਾਈਲ ਚੁਣੋ:", "hinglish": "Audio file chunein:", "hi": "ऑडियो फाइल चुनें:"},
    "submit": {"en": "Get Advisory", "pa": "ਸਲਾਹ ਲਵੋ", "hinglish": "Salah lein", "hi": "परामर्श लें"},
    "clear": {"en": "Clear", "pa": "ਸਾਫ਼ ਕਰੋ", "hinglish": "Saaf karein", "hi": "साफ़ करें"},
    "spinner_audio": {
        "en": "Transcribing your voice note and searching the knowledge base...",
        "pa": "ਆਡੀਓ ਨੂੰ ਲਿਖਤ ਵਿੱਚ ਬਦਲ ਕੇ ਖੇਤੀ ਗਿਆਨ-ਕੋਸ਼ ਵਿੱਚੋਂ ਖੋਜ ਕੀਤੀ ਜਾ ਰਹੀ ਹੈ...",
        "hinglish": "Audio ko text mein badal kar krishi gyaankosh se jaanch ho rahi hai...",
        "hi": "ऑडियो वाक्-से-पाठ (STT) एवं कृषि ज्ञानकोश से विश्लेषण हो रहा है...",
    },
    "spinner_text": {
        "en": "Preparing verified advice from ICAR/PAU and weather sources...",
        "pa": "ਖੇਤੀ ਗਿਆਨ-ਕੋਸ਼ (ICAR/PAU/ਮੌਸਮ) ਤੋਂ ਪ੍ਰਮਾਣਿਤ ਸਲਾਹ ਤਿਆਰ ਕੀਤੀ ਜਾ ਰਹੀ ਹੈ...",
        "hinglish": "Krishi gyaankosh (ICAR/PAU/mausam) se pramanit salah taiyaar ki ja rahi hai...",
        "hi": "कृषि ज्ञानकोश (ICAR/PAU/मौसम) से सत्यापित परामर्श तैयार किया जा रहा है...",
    },
    "warn_empty": {
        "en": "Please type a question or upload an audio file.",
        "pa": "ਕਿਰਪਾ ਕਰਕੇ ਸਵਾਲ ਲਿਖੋ ਜਾਂ ਆਡੀਓ ਫ਼ਾਈਲ ਅੱਪਲੋਡ ਕਰੋ।",
        "hinglish": "Kripya sawal likhein ya audio file upload karein.",
        "hi": "कृपया टेक्स्ट लिखें या ऑडियो फाइल अपलोड करें।",
    },
    "metric_intent": {"en": "Detected topic", "pa": "ਪਛਾਣਿਆ ਵਿਸ਼ਾ", "hinglish": "Pehchana gaya vishay", "hi": "पहचाना गया विषय"},
    "metric_latency": {"en": "Response time", "pa": "ਜਵਾਬ ਦਾ ਸਮਾਂ", "hinglish": "Jawab ka samay", "hi": "प्रतिक्रिया समय"},
    "metric_crop": {"en": "Crop / Region", "pa": "ਫ਼ਸਲ / ਖੇਤਰ", "hinglish": "Fasal / Kshetra", "hi": "फसल / क्षेत्र"},
    "general": {"en": "General", "pa": "ਆਮ", "hinglish": "Samanya", "hi": "सामान्य"},
    "metric_grounding": {"en": "Grounding", "pa": "ਪ੍ਰਮਾਣਿਕਤਾ", "hinglish": "Pramanikta", "hi": "प्रमाणीकरण"},
    "grounded_yes": {"en": "Fully verified", "pa": "ਪੂਰੀ ਤਰ੍ਹਾਂ ਪ੍ਰਮਾਣਿਤ", "hinglish": "Poori tarah pramanit", "hi": "पूर्णतः प्रमाणित"},
    "grounded_partial": {"en": "Partially sourced", "pa": "ਅੰਸ਼ਕ ਹਵਾਲਾ", "hinglish": "Aanshik sandarbh", "hi": "आंशिक संदर्भ"},
    "weather_metrics_header": {
        "en": "Weather & Spray Conditions",
        "pa": "ਮੌਸਮ ਅਤੇ ਛਿੜਕਾਅ ਹਾਲਾਤ",
        "hinglish": "Mausam aur Chhidkaav Halaat",
        "hi": "मौसम एवं छिड़काव विश्लेषण",
    },
    "note_template_llm_failed": {
        "en": (
            "The AI service is busy right now, so this answer was taken directly from the advisory text "
            "without AI. It may not match your question as closely. Please try again in a minute."
        ),
        "pa": (
            "AI ਸੇਵਾ ਇਸ ਵੇਲੇ ਰੁੱਝੀ ਹੋਈ ਹੈ, ਇਸ ਲਈ ਇਹ ਜਵਾਬ AI ਤੋਂ ਬਿਨਾਂ ਸਿੱਧਾ ਸਲਾਹ-ਪੱਤਰ ਵਿੱਚੋਂ ਲਿਆ ਗਿਆ ਹੈ। "
            "ਹੋ ਸਕਦਾ ਹੈ ਇਹ ਤੁਹਾਡੇ ਸਵਾਲ ਨਾਲ ਪੂਰਾ ਮੇਲ ਨਾ ਖਾਵੇ। ਕਿਰਪਾ ਕਰਕੇ ਇੱਕ ਮਿੰਟ ਬਾਅਦ ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ।"
        ),
        "hinglish": (
            "AI service abhi vyast hai, isliye yeh jawab bina AI ke seedha salah-patra se liya gaya hai. "
            "Ho sakta hai yeh aapke sawal se poori tarah mel na khaye. Kripya ek minute baad dobara koshish karein."
        ),
        "hi": (
            "AI सेवा अभी व्यस्त है, इसलिए यह उत्तर बिना AI के सीधे परामर्श-पत्र से लिया गया है। "
            "हो सकता है यह आपके प्रश्न से पूरी तरह मेल न खाए। कृपया एक मिनट बाद फिर से प्रयास करें।"
        ),
    },
    "note_template_offline": {
        "en": (
            "AI answers are turned off, so this answer was taken directly from the advisory text. "
            "It may not match your question as closely."
        ),
        "pa": (
            "AI ਜਵਾਬ ਬੰਦ ਹਨ, ਇਸ ਲਈ ਇਹ ਜਵਾਬ ਸਿੱਧਾ ਸਲਾਹ-ਪੱਤਰ ਵਿੱਚੋਂ ਲਿਆ ਗਿਆ ਹੈ। "
            "ਹੋ ਸਕਦਾ ਹੈ ਇਹ ਤੁਹਾਡੇ ਸਵਾਲ ਨਾਲ ਪੂਰਾ ਮੇਲ ਨਾ ਖਾਵੇ।"
        ),
        "hinglish": (
            "AI jawab band hain, isliye yeh jawab seedha salah-patra se liya gaya hai. "
            "Ho sakta hai yeh aapke sawal se poori tarah mel na khaye."
        ),
        "hi": (
            "AI उत्तर बंद हैं, इसलिए यह उत्तर सीधे परामर्श-पत्र से लिया गया है। "
            "हो सकता है यह आपके प्रश्न से पूरी तरह मेल न खाए।"
        ),
    },
    "badge_verified": {
        "en": "ICAR · PAU · CIBRC verified",
        "pa": "ICAR · PAU · CIBRC ਪ੍ਰਮਾਣਿਤ",
        "hinglish": "ICAR · PAU · CIBRC pramanit",
        "hi": "ICAR · PAU · CIBRC प्रमाणित",
    },
    "badge_languages": {"en": "4 languages · voice", "pa": "4 ਭਾਸ਼ਾਵਾਂ · ਆਵਾਜ਼", "hinglish": "4 bhashayein · awaaz", "hi": "4 भाषाएँ · आवाज़"},
    "badge_weather": {"en": "Live weather", "pa": "ਲਾਈਵ ਮੌਸਮ", "hinglish": "Live mausam", "hi": "लाइव मौसम"},
    "empty_state": {
        "en": "Ask your question above, or tap one of the sample questions, to get verified advice.",
        "pa": "ਪ੍ਰਮਾਣਿਤ ਸਲਾਹ ਲਈ ਉੱਪਰ ਆਪਣਾ ਸਵਾਲ ਪੁੱਛੋ, ਜਾਂ ਕੋਈ ਉਦਾਹਰਨ ਸਵਾਲ ਦਬਾਓ।",
        "hinglish": "Pramanit salah ke liye upar apna sawal poochein, ya koi udaharan sawal dabayein.",
        "hi": "प्रमाणित सलाह के लिए ऊपर अपना प्रश्न पूछें, या कोई उदाहरण प्रश्न दबाएँ।",
    },
    "photo_header": {
        "en": "Diagnose a crop problem from a photo",
        "pa": "ਫ਼ੋਟੋ ਤੋਂ ਫ਼ਸਲ ਦੀ ਬਿਮਾਰੀ ਪਛਾਣੋ",
        "hinglish": "Photo se fasal ki bimari pehchanein",
        "hi": "फोटो से फसल की बीमारी पहचानें",
    },
    "photo_upload": {
        "en": "Take or choose a clear, close photo of the affected leaves, stem or grain",
        "pa": "ਪ੍ਰਭਾਵਿਤ ਪੱਤਿਆਂ, ਤਣੇ ਜਾਂ ਦਾਣਿਆਂ ਦੀ ਸਾਫ਼, ਨੇੜੇ ਤੋਂ ਫ਼ੋਟੋ ਲਓ ਜਾਂ ਚੁਣੋ",
        "hinglish": "Prabhavit patton, tane ya daanon ki saaf, paas se photo lein ya chunein",
        "hi": "प्रभावित पत्तियों, तने या दानों की साफ़, पास से फोटो लें या चुनें",
    },
    "photo_question": {
        "en": "Optional: describe the problem",
        "pa": "ਵਿਕਲਪਿਕ: ਸਮੱਸਿਆ ਬਾਰੇ ਦੱਸੋ",
        "hinglish": "Vaikalpik: samasya ke baare mein batayein",
        "hi": "वैकल्पिक: समस्या के बारे में बताएँ",
    },
    "photo_submit": {"en": "Diagnose photo", "pa": "ਫ਼ੋਟੋ ਦੀ ਜਾਂਚ ਕਰੋ", "hinglish": "Photo jaanchein", "hi": "फोटो जाँचें"},
    "spinner_photo": {
        "en": "Looking at the photo and checking verified advisories...",
        "pa": "ਫ਼ੋਟੋ ਦੇਖ ਕੇ ਪ੍ਰਮਾਣਿਤ ਸਲਾਹਾਂ ਜਾਂਚੀਆਂ ਜਾ ਰਹੀਆਂ ਹਨ...",
        "hinglish": "Photo dekh kar pramanit salah jaanchi ja rahi hai...",
        "hi": "फोटो देखकर प्रमाणित सलाह जाँची जा रही है...",
    },
    "photo_user_label": {"en": "(photo)", "pa": "(ਫ਼ੋਟੋ)", "hinglish": "(photo)", "hi": "(फोटो)"},
    "photo_result": {
        "en": "**Photo diagnosis (AI estimate):** most likely **{problem}** on {crop} ({confidence} confidence).\n\n{summary}",
        "pa": "**ਫ਼ੋਟੋ ਜਾਂਚ (AI ਅੰਦਾਜ਼ਾ):** ਸੰਭਾਵਤ ਤੌਰ 'ਤੇ {crop} ਵਿੱਚ **{problem}** ({confidence} ਭਰੋਸਾ)।\n\n{summary}",
        "hinglish": "**Photo jaanch (AI andaaza):** sambhavtah {crop} mein **{problem}** ({confidence} bharosa).\n\n{summary}",
        "hi": "**फोटो जाँच (AI अनुमान):** संभवतः {crop} में **{problem}** ({confidence} भरोसा)।\n\n{summary}",
    },
    "confidence_high": {"en": "high", "pa": "ਉੱਚ", "hinglish": "zyada", "hi": "उच्च"},
    "confidence_medium": {"en": "medium", "pa": "ਦਰਮਿਆਨਾ", "hinglish": "madhyam", "hi": "मध्यम"},
    "confidence_low": {"en": "low", "pa": "ਘੱਟ", "hinglish": "kam", "hi": "कम"},
    "photo_not_plant": {
        "en": "This photo doesn't seem to show a crop plant. Please send a clear, close photo of the affected leaves, stem or grain.",
        "pa": "ਇਹ ਫ਼ੋਟੋ ਫ਼ਸਲ ਦੇ ਪੌਦੇ ਦੀ ਨਹੀਂ ਲੱਗਦੀ। ਕਿਰਪਾ ਕਰਕੇ ਪ੍ਰਭਾਵਿਤ ਪੱਤਿਆਂ, ਤਣੇ ਜਾਂ ਦਾਣਿਆਂ ਦੀ ਸਾਫ਼, ਨੇੜੇ ਤੋਂ ਫ਼ੋਟੋ ਭੇਜੋ।",
        "hinglish": "Yeh photo fasal ke paudhe ki nahi lagti. Kripya prabhavit patton, tane ya daanon ki saaf, paas se photo bhejein.",
        "hi": "यह फोटो फसल के पौधे की नहीं लगती। कृपया प्रभावित पत्तियों, तने या दानों की साफ़, पास से फोटो भेजें।",
    },
    "photo_unclear": {
        "en": "I couldn't identify the problem from this photo. Please send a closer, well-lit photo of the affected part, or contact your nearest Krishi Vigyan Kendra (KVK).",
        "pa": "ਮੈਂ ਇਸ ਫ਼ੋਟੋ ਤੋਂ ਸਮੱਸਿਆ ਪਛਾਣ ਨਹੀਂ ਸਕਿਆ। ਕਿਰਪਾ ਕਰਕੇ ਪ੍ਰਭਾਵਿਤ ਹਿੱਸੇ ਦੀ ਨੇੜੇ ਤੋਂ, ਚੰਗੀ ਰੌਸ਼ਨੀ ਵਿੱਚ ਫ਼ੋਟੋ ਭੇਜੋ, ਜਾਂ ਆਪਣੇ ਨੇੜਲੇ ਕ੍ਰਿਸ਼ੀ ਵਿਗਿਆਨ ਕੇਂਦਰ (KVK) ਨਾਲ ਸੰਪਰਕ ਕਰੋ।",
        "hinglish": "Main is photo se samasya pehchan nahi paya. Kripya prabhavit hisse ki paas se, achhi roshni mein photo bhejein, ya apne nazdeeki Krishi Vigyan Kendra (KVK) se sampark karein.",
        "hi": "मैं इस फोटो से समस्या पहचान नहीं पाया। कृपया प्रभावित हिस्से की पास से, अच्छी रोशनी में फोटो भेजें, या अपने नज़दीकी कृषि विज्ञान केंद्र (KVK) से संपर्क करें।",
    },
    "photo_healthy": {
        "en": "The plant in this photo looks healthy. If you still see a problem, send a closer photo of the affected part.",
        "pa": "ਇਸ ਫ਼ੋਟੋ ਵਿੱਚ ਪੌਦਾ ਤੰਦਰੁਸਤ ਲੱਗਦਾ ਹੈ। ਜੇ ਫਿਰ ਵੀ ਕੋਈ ਸਮੱਸਿਆ ਦਿਸਦੀ ਹੈ, ਤਾਂ ਪ੍ਰਭਾਵਿਤ ਹਿੱਸੇ ਦੀ ਨੇੜੇ ਤੋਂ ਫ਼ੋਟੋ ਭੇਜੋ।",
        "hinglish": "Is photo mein paudha swasth lagta hai. Agar phir bhi koi samasya dikhe, to prabhavit hisse ki paas se photo bhejein.",
        "hi": "इस फोटो में पौधा स्वस्थ लगता है। अगर फिर भी कोई समस्या दिखे, तो प्रभावित हिस्से की पास से फोटो भेजें।",
    },
    "photo_not_covered": {
        "en": "Our verified advisories don't cover this crop or problem yet, so I can't recommend a treatment. Please contact your nearest Krishi Vigyan Kendra (KVK).",
        "pa": "ਸਾਡੀਆਂ ਪ੍ਰਮਾਣਿਤ ਸਲਾਹਾਂ ਵਿੱਚ ਅਜੇ ਇਹ ਫ਼ਸਲ ਜਾਂ ਸਮੱਸਿਆ ਸ਼ਾਮਲ ਨਹੀਂ, ਇਸ ਲਈ ਮੈਂ ਇਲਾਜ ਨਹੀਂ ਦੱਸ ਸਕਦਾ। ਕਿਰਪਾ ਕਰਕੇ ਆਪਣੇ ਨੇੜਲੇ ਕ੍ਰਿਸ਼ੀ ਵਿਗਿਆਨ ਕੇਂਦਰ (KVK) ਨਾਲ ਸੰਪਰਕ ਕਰੋ।",
        "hinglish": "Hamari pramanit salah mein abhi yeh fasal ya samasya shamil nahi hai, isliye main ilaaj nahi bata sakta. Kripya apne nazdeeki Krishi Vigyan Kendra (KVK) se sampark karein.",
        "hi": "हमारी प्रमाणित सलाह में अभी यह फसल या समस्या शामिल नहीं है, इसलिए मैं इलाज नहीं बता सकता। कृपया अपने नज़दीकी कृषि विज्ञान केंद्र (KVK) से संपर्क करें।",
    },
    "photo_disclaimer": {
        "en": "This photo diagnosis is an AI estimate, not a lab test. Confirm with your local KVK or agriculture officer before spraying.",
        "pa": "ਇਹ ਫ਼ੋਟੋ ਜਾਂਚ ਇੱਕ AI ਅੰਦਾਜ਼ਾ ਹੈ, ਲੈਬ ਟੈਸਟ ਨਹੀਂ। ਛਿੜਕਾਅ ਤੋਂ ਪਹਿਲਾਂ ਆਪਣੇ ਨੇੜਲੇ KVK ਜਾਂ ਖੇਤੀਬਾੜੀ ਅਫ਼ਸਰ ਤੋਂ ਪੁਸ਼ਟੀ ਕਰੋ।",
        "hinglish": "Yeh photo jaanch ek AI andaaza hai, lab test nahi. Chhidkaav se pehle apne local KVK ya krishi adhikari se pushti karein.",
        "hi": "यह फोटो जाँच एक AI अनुमान है, लैब टेस्ट नहीं। छिड़काव से पहले अपने स्थानीय KVK या कृषि अधिकारी से पुष्टि करें।",
    },
    "photo_failed": {
        "en": "Sorry, I couldn't analyse the photo right now. Please try again, or describe the problem in words.",
        "pa": "ਮਾਫ਼ ਕਰਨਾ, ਮੈਂ ਇਸ ਵੇਲੇ ਫ਼ੋਟੋ ਦੀ ਜਾਂਚ ਨਹੀਂ ਕਰ ਸਕਿਆ। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ, ਜਾਂ ਸਮੱਸਿਆ ਸ਼ਬਦਾਂ ਵਿੱਚ ਦੱਸੋ।",
        "hinglish": "Maaf kijiye, abhi photo ki jaanch nahi ho payi. Kripya dobara koshish karein, ya samasya shabdon mein batayein.",
        "hi": "क्षमा करें, अभी फोटो की जाँच नहीं हो पाई। कृपया फिर से कोशिश करें, या समस्या शब्दों में बताएँ।",
    },
    "record_label": {
        "en": "Or ask by voice: tap the microphone, speak, then tap stop",
        "pa": "ਜਾਂ ਬੋਲ ਕੇ ਪੁੱਛੋ: ਮਾਈਕ ਦਬਾਓ, ਬੋਲੋ, ਫਿਰ ਰੋਕੋ ਦਬਾਓ",
        "hinglish": "Ya bol kar poochein: mic dabayein, boliye, phir stop dabayein",
        "hi": "या बोलकर पूछें: माइक दबाएँ, बोलें, फिर रोकें दबाएँ",
    },
    "upload_instead": {
        "en": "Upload a recorded voice note instead",
        "pa": "ਜਾਂ ਰਿਕਾਰਡ ਕੀਤਾ ਆਵਾਜ਼ ਸੁਨੇਹਾ ਅੱਪਲੋਡ ਕਰੋ",
        "hinglish": "Ya record kiya hua voice note upload karein",
        "hi": "या रिकॉर्ड किया हुआ वॉइस नोट अपलोड करें",
    },
    "speaking": {"en": "Preparing the spoken answer...", "pa": "ਆਵਾਜ਼ ਵਿੱਚ ਜਵਾਬ ਤਿਆਰ ਹੋ ਰਿਹਾ ਹੈ...", "hinglish": "Awaaz mein jawab taiyaar ho raha hai...", "hi": "आवाज़ में उत्तर तैयार हो रहा है..."},
    "voice_not_understood": {
        "en": "(voice message)",
        "pa": "(ਆਵਾਜ਼ ਸੁਨੇਹਾ)",
        "hinglish": "(voice message)",
        "hi": "(आवाज़ संदेश)",
    },
    "chat_header": {
        "en": "💬 Ask KisanSahayak",
        "pa": "💬 ਕਿਸਾਨ ਸਹਾਇਕ ਨੂੰ ਪੁੱਛੋ",
        "hinglish": "💬 KisanSahayak se poochein",
        "hi": "💬 किसान सहायक से पूछें",
    },
    "new_chat": {"en": "🔄 New conversation", "pa": "🔄 ਨਵੀਂ ਗੱਲਬਾਤ", "hinglish": "🔄 Nayi baatcheet", "hi": "🔄 नई बातचीत"},
    "chat_welcome": {
        "en": (
            "Namaste! Ask me about your crops, pests, pesticides or the weather. "
            "You can ask follow-up questions too, like *\"What is the dose?\"* or *\"And in Sangrur?\"*"
        ),
        "pa": (
            "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਆਪਣੀ ਫ਼ਸਲ, ਕੀੜਿਆਂ, ਦਵਾਈਆਂ ਜਾਂ ਮੌਸਮ ਬਾਰੇ ਪੁੱਛੋ। "
            "ਤੁਸੀਂ ਅਗਲਾ ਸਵਾਲ ਵੀ ਪੁੱਛ ਸਕਦੇ ਹੋ, ਜਿਵੇਂ *\"ਖੁਰਾਕ ਕਿੰਨੀ ਹੈ?\"* ਜਾਂ *\"ਅਤੇ ਸੰਗਰੂਰ ਵਿੱਚ?\"*"
        ),
        "hinglish": (
            "Namaste! Apni fasal, keedon, dawaiyon ya mausam ke baare mein poochein. "
            "Aap aage ka sawal bhi pooch sakte hain, jaise *\"Dose kitni hai?\"* ya *\"Aur Sangrur mein?\"*"
        ),
        "hi": (
            "नमस्ते! अपनी फसल, कीटों, दवाइयों या मौसम के बारे में पूछें। "
            "आप आगे का सवाल भी पूछ सकते हैं, जैसे *\"खुराक कितनी है?\"* या *\"और संगरूर में?\"*"
        ),
    },
    "details_header": {"en": "Details", "pa": "ਵੇਰਵੇ", "hinglish": "Vivaran", "hi": "विवरण"},
    "voice_unavailable": {
        "en": "Spoken answers are not available in this language yet.",
        "pa": "ਇਸ ਭਾਸ਼ਾ ਵਿੱਚ ਆਵਾਜ਼ ਵਾਲੇ ਜਵਾਬ ਅਜੇ ਉਪਲਬਧ ਨਹੀਂ ਹਨ।",
        "hinglish": "Is bhasha mein awaaz wale jawab abhi uplabdh nahi hain.",
        "hi": "इस भाषा में आवाज़ वाले उत्तर अभी उपलब्ध नहीं हैं।",
    },
    "response_header": {"en": "Verified Advice", "pa": "ਪ੍ਰਮਾਣਿਤ ਸਲਾਹ", "hinglish": "Pramanit Salah", "hi": "सत्यापित परामर्श"},
    "listen_header": {"en": "Listen to the advice", "pa": "ਆਵਾਜ਼ ਵਿੱਚ ਸੁਣੋ", "hinglish": "Awaaz mein sunein", "hi": "आवाज़ में सुनें"},
    "safety_header": {
        "en": "Safety Warnings",
        "pa": "ਸੁਰੱਖਿਆ ਹਦਾਇਤਾਂ ਅਤੇ ਚੇਤਾਵਨੀਆਂ",
        "hinglish": "Suraksha Nirdesh aur Chetavaniyan",
        "hi": "सुरक्षा निर्देश एवं चेतावनियां",
    },
    "sources_header": {"en": "Official Sources", "pa": "ਅਧਿਕਾਰਤ ਸਰੋਤ", "hinglish": "Aadhikarik Sandarbh", "hi": "आधिकारिक संदर्भ"},
    "evidence_header": {
        "en": "Source text used (evidence)",
        "pa": "ਗਿਆਨ-ਕੋਸ਼ ਵਿੱਚੋਂ ਲਿਆ ਮੂਲ ਹਵਾਲਾ",
        "hinglish": "Gyaankosh se liya gaya mool sandarbh",
        "hi": "ज्ञानकोश से पुनर्प्राप्त मूल संदर्भ",
    },
    "sidebar_weather_header": {
        "en": "🌦️ Quick Farm Weather",
        "pa": "🌦️ ਝਟਪਟ ਮੌਸਮ ਜਾਂਚ",
        "hinglish": "🌦️ Turant Mausam Jaanch",
        "hi": "🌦️ त्वरित मौसम जांच",
    },
    "select_district": {"en": "Select your district:", "pa": "ਆਪਣਾ ਜ਼ਿਲ੍ਹਾ ਚੁਣੋ:", "hinglish": "Apna zila chunein:", "hi": "अपना जिला चुनें:"},
    "check_weather": {
        "en": "Check weather & spray window",
        "pa": "ਮੌਸਮ ਅਤੇ ਛਿੜਕਾਅ ਦਾ ਸਮਾਂ ਦੇਖੋ",
        "hinglish": "Mausam aur chhidkaav ka samay dekhein",
        "hi": "मौसम व छिड़काव खिड़की देखें",
    },
    "weather_card_title": {"en": "{district} weather", "pa": "{district} ਮੌਸਮ", "hinglish": "{district} mausam", "hi": "{district} मौसम"},
    "system_status_header": {"en": "⚙️ System Status", "pa": "⚙️ ਸਿਸਟਮ ਸਥਿਤੀ", "hinglish": "⚙️ System Sthiti", "hi": "⚙️ सिस्टम स्थिति"},
    "samples_header": {"en": "💡 Sample Questions", "pa": "💡 ਉਦਾਹਰਨ ਸਵਾਲ", "hinglish": "💡 Udaharan Sawal", "hi": "💡 उदाहरण प्रश्न"},
    "sidebar_caption": {
        "en": "Grounded strictly in ICAR, PAU Ludhiana, Open-Meteo, and CIBRC advisories.",
        "pa": "ਸਿਰਫ਼ ICAR, PAU ਲੁਧਿਆਣਾ, Open-Meteo ਅਤੇ CIBRC ਸਲਾਹਾਂ ਉੱਤੇ ਅਧਾਰਿਤ।",
        "hinglish": "Sirf ICAR, PAU Ludhiana, Open-Meteo aur CIBRC advisories par aadharit.",
        "hi": "केवल ICAR, PAU लुधियाना, Open-Meteo और CIBRC परामर्शों पर आधारित।",
    },
}

SAMPLE_QUESTIONS: Dict[str, List[str]] = {
    "en": [
        "What are the symptoms and treatment of yellow rust in wheat?",
        "What's the weather in Ludhiana today, can I spray pesticide?",
        "How to control aphids in mustard crop?",
        "What is the treatment for brown planthopper (BPH) in paddy?",
        "Can I use Monocrotophos on brinjal or cauliflower?",
        "What is the recommended time for wheat irrigation?",
        "How to control pink bollworm in cotton?",
    ],
    "pa": [
        "ਕਣਕ ਵਿੱਚ ਪੀਲੀ ਕੁੰਗੀ ਦੇ ਲੱਛਣ ਅਤੇ ਇਲਾਜ ਕੀ ਹਨ?",
        "ਲੁਧਿਆਣਾ ਵਿੱਚ ਅੱਜ ਮੌਸਮ ਕਿਹੋ ਜਿਹਾ ਹੈ, ਕੀ ਛਿੜਕਾਅ ਕਰ ਸਕਦੇ ਹਾਂ?",
        "ਸਰ੍ਹੋਂ ਵਿੱਚ ਚੇਪੇ ਦੀ ਰੋਕਥਾਮ ਕਿਵੇਂ ਕਰੀਏ?",
        "ਝੋਨੇ ਵਿੱਚ ਭੂਰੇ ਟਿੱਡੇ (BPH) ਦਾ ਕੀ ਇਲਾਜ ਹੈ?",
        "ਕੀ ਬੈਂਗਣ ਜਾਂ ਗੋਭੀ ਉੱਤੇ ਮੋਨੋਕ੍ਰੋਟੋਫ਼ਾਸ (Monocrotophos) ਪਾ ਸਕਦੇ ਹਾਂ?",
        "ਕਣਕ ਨੂੰ ਪਾਣੀ ਦੇਣ ਦਾ ਸਹੀ ਸਮਾਂ ਕੀ ਹੈ?",
        "ਨਰਮੇ ਵਿੱਚ ਗੁਲਾਬੀ ਸੁੰਡੀ ਦੀ ਰੋਕਥਾਮ ਕਿਵੇਂ ਕਰੀਏ?",
    ],
    "hinglish": [
        "Gehun mein peeli kungi ke lakshan aur ilaj kya hain?",
        "Ludhiana mein aaj mausam kaisa hai, kya spray kar sakte hain?",
        "Sarson mein chepa ka ilaj kya hai?",
        "Dhan mein bhoora tilla (BPH) ka kya ilaj hai?",
        "Kya baingan ya gobhi mein Monocrotophos daal sakte hain?",
        "Gehun mein sinchai ka sahi samay kya hai?",
        "Kapas mein gulabi sundhi ki roktham kaise karein?",
    ],
    "hi": [
        "गेहूं में पीली कुंगी (Yellow Rust) के लक्षण और उपचार क्या हैं?",
        "लुधियाना में आज मौसम कैसा है, क्या कीटनाशक छिड़काव कर सकते हैं?",
        "सरसों में माहू (चेपा) की रोकथाम कैसे करें?",
        "धान में भूरा तेला (BPH) का क्या इलाज है?",
        "क्या बैंगन या गोभी में मोनोक्रोटोफॉस (Monocrotophos) डाल सकते हैं?",
        "गेहूं में सिंचाई का सही समय क्या है?",
        "कपास में गुलाबी सुंडी (Pink Bollworm) की रोकथाम कैसे करें?",
    ],
}


def normalize_language(language: str) -> str:
    """Map a language code or name to a supported code, defaulting to Hindi."""
    lang = (language or "").lower().strip()
    aliases = {"english": "en", "punjabi": "pa", "panjabi": "pa", "hindi": "hi"}
    lang = aliases.get(lang, lang)
    return lang if lang in LANGUAGES else "hi"


def t(key: str, language: str, **kwargs) -> str:
    """Look up a user-facing string in the given language (falls back to English)."""
    entry = STRINGS[key]
    text = entry.get(normalize_language(language), entry["en"])
    return text.format(**kwargs) if kwargs else text
