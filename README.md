scalepot
---

You can scale your ec2 instances automatically using scalepot.

---

Getting Started
---

* Install `scalepot`.

        $ git clone git@github.com:limsangjin12/scalepot.git && cd scalepot
        $ python setup.py install

    or

        $ pip install scalepot

* Write `scalepot.py`.

        from scalepot.api import scale, State, g as scaleinfo        

        def deploy_worker(ip):
            # deploy worker here
            pass

        @scale
        def scale():
            if scaleinfo.state == State.SCALE_OUT:
                if scaleinfo.role.name == 'worker':
                    ip = scaleinfo.role.instance.ip_address
                    deploy_worker(ip)

* Write `scalepot.yml` in the same path.

        az: ap-northeast-1
        roles:
        - name: worker
          type: c1.medium
          min: 2
          max: 5
          ami: ami-86db6187
          option: spot # on-demand or spot
          cooltime: 20 # minutes between checking
                       # each instances
          placement: b

* You need `~/.boto` file also.

        [Credentials]
        aws_access_key_id = (your access key id)
        aws_secret_access_key = (your secret access key)

* Then,

        $ scalepot

---

Define custom checking function
---

* Define a function with `check` decorator.

        from scalepot.api import scale, State, g as scaleinfo
        from scalepot.api import check

        def deploy_worker(ip):
            # deploy worker here
            pass

        @scale
        def scale():
            if scaleinfo.state == State.SCALE_OUT:
                if scaleinfo.role.name == 'worker':
                    ip = ip = scaleinfo.role.instance.ip_address
                    deploy_worker(ip)

        @check
        def check():
            if scaleinfo.count < 3:
                return State.SCALE_OUT
            return State.NORMAL

---

Tips
---

* `scalepot` basically uses `CPUUtilization` metric for last 10 minutes as a default to scale-out/down.

* You can define `scale_out_threshold` (default value is 60) and `scale_down_ratio` (default value is 0.7) on your `scalepot.yml` file.

* `scalepot.api.g.instance` is a [`boto.ec2.instance.Instance`](http://boto.readthedocs.org/en/latest/ref/ec2.html#module-boto.ec2.instance) object.

* `scalepot.api.State` is implemented like below.

        class State(object):
            SCALE_OUT = 'SHOULD SCALE OUT'
            SCALE_DOWN = 'SHOULD SCALE DOWN'
            MAX_LIMIT = 'MAX LIMIT REACHED'
            MIN_LIMIT = 'MIN LIMIT REACHED'
            NORMAL = 'NORMAL'

* To show more console options,

        $ scalepot -h

