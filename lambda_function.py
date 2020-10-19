import json
import boto3
import requests
from datetime import datetime, timedelta
import os
import pandas as pd


def read_s3_file():
    s3 = boto3.resource('s3')
    s3_key = os.environ['S3_KEY']
    print(s3_key)
    obj = s3.Object('immoviewer-ai-research', os.environ['S3_KEY'])
    from_s3 = obj.get()['Body'].read().decode('utf-8')
    print('downloaded file from s3')
    print(from_s3)
    print(type(from_s3))
    return from_s3


def download_last_100(prev_responses, need_lenght):
    client = boto3.client('ce')

    now_date = datetime.now()
    now_date_string = now_date.strftime("%Y-%m-%d")  # TODAY

    if len(prev_responses) < need_lenght:  # by default should be == 100

        previous_date = now_date - 100 * timedelta(hours=24)
        previous_date_string = previous_date.strftime("%Y-%m-%d")

        response = client.get_cost_and_usage(TimePeriod={
            'Start': f'{previous_date_string}',
            'End': f'{now_date_string}'
        }, Granularity='DAILY',
            Metrics=['NetAmortizedCost'])

        new_prev_responses = json.loads(str(json.dumps(response)))['ResultsByTime']
        print(len(new_prev_responses))
        print('resp_type=', type(new_prev_responses), 'new_resp=', new_prev_responses)
        return new_prev_responses
    else:
        previous_date = now_date - timedelta(hours=24)
        previous_date_string = previous_date.strftime("%Y-%m-%d")

        response = client.get_cost_and_usage(TimePeriod={
            'Start': f'{previous_date_string}',
            'End': f'{now_date_string}'
        }, Granularity='DAILY',
            Metrics=['NetAmortizedCost'])

        resp = json.loads(str(json.dumps(response)))['ResultsByTime']
        print(type(resp), 'new_resp= ', resp)
        print(type(prev_responses), 'prev_resp=', prev_responses)
        new_prev_responses = json.loads(prev_responses)
        print(type(new_prev_responses), 'after_loads=', new_prev_responses)
        new_prev_responses.append(resp[0])
        print('after-append', new_prev_responses)
        del new_prev_responses[0]
        print('len_new_previous=', len(new_prev_responses))
        print('response_type=', type(new_prev_responses), 'edited_response=', new_prev_responses)
        return new_prev_responses


def analyze_w_last100(last_100_list):
    print(last_100_list)
    print(type(last_100_list))
    df_start = pd.DataFrame((obj['TimePeriod']['Start'],
                             obj['Total']['NetAmortizedCost']['Amount']) for obj in last_100_list)

    df_start.columns = ['start', 'amount']
    df_start = df_start.astype({'amount': 'float64'})
    last_response = df_start.loc[int(df_start.shape[0]) - 1]

    df_start_first_only = df_start[df_start['start'].str.endswith('01')].reset_index(drop=True)
    if df_start_first_only.shape[0] > 1:
        df_start_first_only = df_start_first_only.drop(df_start_first_only.shape[0] - 1)
    avg_start_only = df_start_first_only['amount'].mean()

    df_not_first = df_start[~df_start['start'].str.endswith('01')].reset_index(drop=True)
    if df_not_first.shape[0] > 1:
        df_not_first = df_not_first.drop(df_not_first.shape[0] - 1)
    avg_not_start = df_not_first['amount'].mean()

    last_response_amount = last_response['amount']

    if last_response['start'].endswith('01') is True:
        if last_response_amount > avg_start_only * 1.1:
            if last_response_amount > avg_start_only * 1.2:
                send_slack_message(
                    'alarm! average begin month daily limit {} USD exceeded higher 20%, by {}%, now –– {} USD'.
                        format(avg_start_only, round(float((last_response_amount / avg_start_only) * 100 - 100), 2),
                               last_response_amount))
            else:
                send_slack_message(
                    'warning! average begin month daily limit {} USD exceeded higher 10%, by {}%, now –– {} USD'.
                        format(avg_start_only, round(float((last_response_amount / avg_start_only) * 100 - 100), 2),
                               last_response_amount))
    else:
        if last_response_amount > avg_not_start * 1.1:
            if last_response_amount > avg_not_start * 1.2:
                send_slack_message('alarm! average daly limit {} USD exceeded by {}%, now –– {} USD'.
                                   format(avg_not_start,
                                          round(float((last_response_amount / avg_not_start) * 100 - 100), 2),
                                          last_response_amount))
            else:
                send_slack_message('warning! average daily limit {} USD exceeded by {}%, now –– {} USD'.
                                   format(avg_not_start,
                                          round(float((last_response_amount / avg_not_start) * 100 - 100), 2),
                                          last_response_amount))
    return last_100_list


def send_slack_message(message):
    slack_url = os.environ['SLACK_HOOK']
    slack_id = os.environ['SLACK_ID']

    message_text = message + ' <@' + slack_id + '>'
    print('msg', message_text)
    data = {'text': message_text}
    requests.post(url=slack_url, data=json.dumps(data))
    print("Send message to slack")


def upload_response_list_to_s3(response_list: list):
    s3 = boto3.resource('s3')
    obj = s3.Object('immoviewer-ai-research', os.environ['S3_KEY'])  # key from env
    print('dumped_list=', json.dumps(response_list))
    print('type_dumped_list', type(json.dumps(response_list)))
    obj.put(Body=json.dumps(response_list))
    print('uploaded new file to s3')


file_from_s3 = read_s3_file()
list_of_100 = download_last_100(file_from_s3, 100)
analyzed_list_of_100 = analyze_w_last100(list_of_100)
upload_response_list_to_s3(analyzed_list_of_100)
