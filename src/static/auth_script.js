/**
 * Copyright 2018, Google LLC
 * Licensed under the Apache License, Version 2.0 (the `License`);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an `AS IS` BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

'use strict';

// Set in templates/auth_token.html based on environment variable in app.yaml
// const FIREBASE_ID_TOKEN = 'id_token';
// Set proxy prefix for local testing behind a reverse proxy
// const PROXY_PREFIX = '';

window.addEventListener('load', function () {
  
  // [START gae_python38_auth_signout]
  document.getElementById('sign-out').onclick = function () {
    firebase.auth().signOut();
  };
  // [END gae_python38_auth_signout]
  //
  // See also https://github.com/firebase/firebaseui-web/tree/master/demo
  //
  // [START gae_python38_auth_UIconfig_variable]
  // FirebaseUI config.
  var uiConfig = {
    signInSuccessUrl: PROXY_PREFIX + '/auth/',
    signInOptions: [
      // Remove any lines corresponding to providers you did not check in
      // the Firebase console.
      firebase.auth.GoogleAuthProvider.PROVIDER_ID,
      //firebase.auth.EmailAuthProvider.PROVIDER_ID,
      //firebaseui.auth.AnonymousAuthProvider.PROVIDER_ID
    ],
    // Terms of service url.
    tosUrl: '<your-tos-url>'
  };
  // [END gae_python38_auth_UIconfig_variable]

  // [START gae_python38_auth_request]
  firebase.auth().onAuthStateChanged(function (user) {
    if (user) {
      // User is signed in, so display the "sign out" button and login info.
      document.getElementById('sign-out').hidden = false;
      document.getElementById('login-info').hidden = false;
      console.log(`Signed in as ${user.displayName} (${user.email})`);
      user.getIdToken().then(function (token) {
        // Add the token to the browser's cookies. The server will then be
        // able to verify the token against the API.
        // SECURITY NOTE: As cookies can easily be modified, only put the
        // token (which is verified server-side) in a cookie; do not add other
        // user information.
        document.cookie = FIREBASE_ID_TOKEN + "=" + token + "; path=" + PROXY_PREFIX + "/";
      });
    } else {
      // User is signed out.
      // Initialize the FirebaseUI Widget using Firebase.
      var ui = new firebaseui.auth.AuthUI(firebase.auth());
      // See also https://github.com/firebase/firebaseui-web/tree/master/demo
      // Disable auto-sign in.
      ui.disableAutoSignIn();
      // Show the Firebase login button.
      ui.start('#firebaseui-auth-container', uiConfig);
      console.log(`Signed in as anonymous`);
      // Update the login state indicators.
      document.getElementById('sign-out').hidden = true;
      document.getElementById('login-info').hidden = true;
      // Clear the token cookie.
      document.cookie = FIREBASE_ID_TOKEN + "=" + "; path=" + PROXY_PREFIX + "/";
    }
  }, function (error) {
    console.log(error);
    alert('Unable to log in: ' + error)
  });
  // [END gae_python38_auth_request]
});
