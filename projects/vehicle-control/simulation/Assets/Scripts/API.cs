﻿using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using JsonFx;

public class DataDefinition {
	public string name;
	public string type;
}

public class API : MonoBehaviour {

	public bool blockOnResponse = false;
	public float updateRate = 30;  // hertz
	public float runSpeed = 1.0f;
	public string serverURL = "http://localhost:8080";

	private bool _isWaitingForResponse;
	private float _lastSyncTime;
	private Dictionary<string, object> _outputData;
	private Dictionary<string, object> _inputData;

	public void SetOutput(string name, object data) {
		_outputData [name] = data;
	}

	public object GetInput(string name) {
		if (_inputData.ContainsKey (name)) {
			return _inputData [name];
		}
		return null;
	}

	public float LastSyncTime() {
		return _lastSyncTime;
	}

	public void Reset() {
		SetOutput("reset", true);
	}

	void ClearOutput() {
		_outputData = new Dictionary<string, object>();
	}

	void ClearInput() {
		_inputData = new Dictionary<string, object>();
	}

	void Clear() {
		ClearOutput();
		ClearInput();
	}

	/* Data transfer */

	IEnumerator Sync() {
		_lastSyncTime = Time.time;
		_isWaitingForResponse = true;
		Time.timeScale = 0f;

		WWWForm form = new WWWForm();
		form.AddField ("outputData", JsonWriter.Serialize(_outputData));
		string pth = "/sync";
		WWW www = new WWW(serverURL + pth, form);
		yield return www;

		_isWaitingForResponse = false;
		if (www.error != null) return false;

		_inputData = JsonReader.Deserialize<Dictionary<string, object>>(www.text);
		ClearOutput();
	}

	/* Events */

	void Start() {
		Clear();
		Reset();
	}

	void Update() {
		if (blockOnResponse && _isWaitingForResponse) {
			Time.timeScale = 0f;
		}
		else {
			Time.timeScale = runSpeed;
		}
	}

	void LateUpdate () {
		if (Time.time - _lastSyncTime < 1 / updateRate) {
			return;
		}

		if (blockOnResponse && _isWaitingForResponse) {
			return;
		}

		StartCoroutine(Sync());
	}


	/* Persistent Singleton */

	private static API _instance;

	public static API instance
	{
		get {
			if (_instance == null) {
				_instance = GameObject.FindObjectOfType<API>();
				DontDestroyOnLoad(_instance.gameObject);
			}

			return _instance;
		}
	}

	void Awake()
	{
		if (_instance == null) {
			_instance = this;
			DontDestroyOnLoad(this);
		}
		else {
			if(this != _instance)
			DestroyImmediate(this.gameObject);
		}
	}

}
