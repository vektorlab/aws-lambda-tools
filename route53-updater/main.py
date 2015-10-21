# -*- coding: utf-8 -*-
"""
Update Route53 Records based on Autoscaling event notifications sent via SNS.
This code was originally inspired by https://objectpartners.com/2015/07/07/aws-tricks-updating-route53-dns-for-autoscalinggroup-using-lambda.
To configure your domain you need to specify a tag per Auto Scaling Group (ASG) "DomainConfig" such as <Route53Zone:domain.com:optional-prefix>.
By default a Route53 entry will be created with the AWS generated EC2 Instance Id .e.g i-abc123456.domain.com. When the server is terminated
it will be removed from the Route53 zone you specified in the ASG tag.
"""

import json

from collections import namedtuple

import boto3


DomainEntry = namedtuple('DomainEntry', ['zone', 'name', 'prefix'])


class Error(Exception):
    pass


class UpdaterClient(object):

    domain_config_tag = 'DomainConfig'
    ttl = 300
    dry_run = False

    def __init__(self, event):
        self._boto = {}
        self.event = event
        self.record = event['Records'][0]
        self.region = self.record['EventSubscriptionArn'].split(':')[3]
        self.message = json.loads(self.record['Sns']['Message'])
        self.instance_id = self.message['EC2InstanceId']
        self.autoscaling_group_name = self.message['AutoScalingGroupName']
        self.event_type = self.message['Event']

    def boto(self, resource):
        if resource not in self._boto:
            self._boto[resource] = boto3.client(resource, region_name=self.region)
        return self._boto[resource]

    def domains(self):
        asg = self.boto('autoscaling').describe_auto_scaling_groups(
            AutoScalingGroupNames=[self.autoscaling_group_name]
        )['AutoScalingGroups'][0]
        tags = [x for x in asg['Tags'] if x['Key'] == self.domain_config_tag]
        if len(tags) != 1:
            raise Error(
                'You must specify the {} tag in your autoscaling group {}'.format(
                    self.domain_config_tag, self.autoscaling_group_name
                )
            )
        for entry in tags[0]['Value'].split(','):
            domain = DomainEntry(*entry.split(':'))
            print('Loaded domain configuration: {}'.format(domain))
            yield domain

    def instance(self):
        ec2 = self.boto('ec2')
        reservation = ec2.describe_instances(InstanceIds=[self.instance_id])
        return reservation['Reservations'][0]['Instances'][0]

    def records(self):
        route53 = self.boto('route53')
        for domain in self.domains():
            zone = route53.get_hosted_zone(Id=domain.zone)
            private = zone['HostedZone']['Config']['PrivateZone']
            name = '{}.{}.'.format(self.instance_id, domain.name)
            record_sets = route53.list_resource_record_sets(
                HostedZoneId=domain.zone,
                StartRecordName=name
            )['ResourceRecordSets']
            record = [x for x in record_sets if x['Name'] == name and x['Type'] == 'A']
            if record:
                record = record[0]
            else:
                instance = self.instance()
                interface = instance['NetworkInterfaces'][0]

                if private:
                    ip_address = interface['PrivateIpAddress']
                else:
                    ip_address = instance['PublicIp']
                record = {
                    'Name': name,
                    'Type': 'A',
                    'TTL': self.ttl,
                    'ResourceRecords': [
                        {
                            'Value': ip_address
                        }
                    ]
                }
            yield domain.zone, record

    def update_tags(self):
        ec2 = self.boto('ec2')
        tags = []
        for index, domain in enumerate(self.domains()):
            server_name = '{}.{}'.format(self.instance_id, domain.name)
            zone_tag = {
                'Key': 'ZoneConfig-{}'.format(index),
                'Value': ':'.join([domain.zone, domain.name, server_name])
            }
            tags.append(zone_tag)
        name_tag = {'Key': 'Name', 'Value': tags[0]['Value'].split(':')[2]}
        tags.append(name_tag)
        kwargs = {'Resources': [self.instance_id], 'Tags': tags}
        print('Updating EC2 instance tags: {}'.format(kwargs))
        if not self.dry_run:
            ec2.create_tags(**kwargs)

    def update_records(self, action):
        route53 = self.boto('route53')
        for zone, record in self.records():
            update = {
                'HostedZoneId': zone,
                'ChangeBatch': {
                    'Comment': 'Automatically updated Route53 Record',
                    'Changes': [
                        {
                            'Action': action,
                            'ResourceRecordSet': record
                        }
                    ]
                }
            }
            print('Executing Route53 update: {}'.format(update))
            if not self.dry_run:
                route53.change_resource_record_sets(**update)


def handler(event, context):

    print('Processing event: {}'.format(event))

    client = UpdaterClient(event)

    if client.event_type == 'autoscaling:EC2_INSTANCE_LAUNCH':
        print('Launch event: {}'.format(client.event_type))
        client.update_tags()
        client.update_records(action='UPSERT')
        print(context.get_remaining_time_in_millis())

    elif client.event_type == 'autoscaling:EC2_INSTANCE_TERMINATE':
        print('Termination event: {}'.format(client.event_type))
        client.update_records(action='DELETE')
        print(context.get_remaining_time_in_millis())

    else:
        raise Error('Unknown event type {}'.format(client.event_type))

