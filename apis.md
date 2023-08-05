/submit/expense/
  POST, returns a json
  input: date (optional), text, amount, token
  output: status:ok

/submit/income/
  POST, returns a json
  input: date (optional), text, amount, token
  output: status:ok

/q/generalstat/
  POST, returns a json
  input: fromdate (optional), todate(optional), token
  output: json from some general stats related to this user