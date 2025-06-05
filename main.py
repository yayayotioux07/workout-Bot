@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("📩 New message received:", data)

    try:
        message_entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in message_entry:
            return "ok", 200

        message = message_entry["messages"][0]
        sender = message["from"]
        msg_type = message["type"]
        text = message.get("text", {}).get("body", "").strip().lower()

        # 💬 Always trigger greeting regardless of state
        if msg_type == "text" and text in ["hi", "hello", "hola", "hey"]:
            send_language_buttons(sender)
            user_states.pop(sender, None)
            return "ok", 200

        user = get_user(sender)

        # 🔄 Restore state if user exists
        if sender not in user_states:
            if user and user[4]:  # has language
                user_states[sender] = {"lang": user[4]}
                if not user[3]:  # not registered
                    send_message(sender, "📝 What's your name?" if user[4] == "en" else "📝 ¿Cuál es tu nombre?")
                    user_states[sender]["step"] = "name"
                else:
                    send_registration_options(sender, user[4])
            else:
                send_language_buttons(sender)
            return "ok", 200

        lang = user_states[sender]["lang"]

        # 🧠 Interactive replies
        if msg_type == "interactive":
            reply_id = message["interactive"]["button_reply"]["id"]
            if reply_id.startswith("lang_"):
                lang = reply_id[-2:]
                save_user(sender, language=lang)
                user_states[sender] = {"lang": lang}
                if user and user[3]:
                    send_registration_options(sender, lang)
                else:
                    send_message(sender, "📝 What's your name?" if lang == "en" else "📝 ¿Cuál es tu nombre?")
                    user_states[sender]["step"] = "name"
            elif reply_id == "re_register":
                send_message(sender, "📝 What's your name?" if lang == "en" else "📝 ¿Cuál es tu nombre?")
                user_states[sender]["step"] = "name"
            elif reply_id == "continue":
                send_message(sender, "💪 Reply with a muscle group (e.g., chest, legs) to get workouts." if lang == "en"
                             else "💪 Responde con un grupo muscular (por ejemplo, pecho, piernas) para comenzar.")
                user_states.pop(sender, None)
            return "ok", 200

        # 📩 Handle registration flow
        if msg_type == "text":
            step = user_states[sender].get("step")
            if step == "name":
                user_states[sender]["name"] = text
                user_states[sender]["step"] = "email"
                send_message(sender, "📧 What's your email?" if lang == "en" else "📧 ¿Cuál es tu correo electrónico?")
            elif step == "email":
                name = user_states[sender].get("name")
                save_user(sender, name=name, email=text, registered=True, language=lang)
                send_message(sender, "✅ You're registered! Reply with a muscle group to get started."
                              if lang == "en" else "✅ ¡Estás registrado! Responde con un grupo muscular para comenzar.")
                user_states.pop(sender, None)

    except Exception as e:
        print("❌ Error:", e)

    return "ok", 200
