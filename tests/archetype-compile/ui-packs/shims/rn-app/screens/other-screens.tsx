// HARNESS STUB (app-level screens): the LoginScreen and SaveOrder button testing/react-native-testing-library.md's
// interaction and accessibility excerpts drive, and the RootStack its navigation excerpt renders.
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";

export function LoginScreen() {
  const [email, setEmail] = useState("");
  const [welcome, setWelcome] = useState(false);
  if (welcome) return <Text>Welcome</Text>;
  return (
    <View>
      <Text nativeID="email-label">Email</Text>
      <TextInput aria-labelledby="email-label" value={email} onChangeText={setEmail} autoComplete="email" />
      <Pressable role="button" aria-label="Sign in" onPress={() => setWelcome(email.includes("@"))}>
        <Text>Sign in</Text>
      </Pressable>
    </View>
  );
}

export function SaveOrderButton() {
  return (
    <Pressable role="button" aria-label="Save order" onPress={() => {}}>
      <Text>Save</Text>
    </Pressable>
  );
}

export declare function RootStack(): React.JSX.Element;
